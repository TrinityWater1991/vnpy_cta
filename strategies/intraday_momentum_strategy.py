"""
日内区间突破策略（IntradayMomentumStrategy）

基于Opening Range Breakout思路，结合日内动量学术研究：
- 日盘开盘后前N分钟形成"开盘区间"（高低点）
- 价格突破区间上沿做多，突破下沿做空
- 收盘前强制平仓，不隔夜持仓
- ATR止损保护

适配：rb99.SHFE 1分钟K线
"""
from datetime import time

from vnpy_ctastrategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class IntradayMomentumStrategy(CtaTemplate):
    """
    日内区间突破策略。

    开盘前N分钟形成价格区间，
    突破区间上下沿时入场，收盘前平仓。
    """

    author: str = "cta_agent"

    # 策略参数
    observation_minutes: int = 55
    range_multiplier: float = 1.0
    atr_window: int = 20
    atr_stop_multiplier: float = 6.5
    fixed_size: int = 1
    exit_hour: int = 14
    exit_minute: int = 45

    # 策略变量
    range_high: float = 0.0
    range_low: float = 0.0
    long_entry: float = 0.0
    short_entry: float = 0.0
    atr_value: float = 0.0
    long_stop: float = 0.0
    short_stop: float = 0.0
    bars_since_open: int = 0
    traded_today: bool = False

    parameters: list[str] = [
        "observation_minutes",
        "range_multiplier",
        "atr_window",
        "atr_stop_multiplier",
        "fixed_size",
        "exit_hour",
        "exit_minute",
    ]

    variables: list[str] = [
        "range_high",
        "range_low",
        "long_entry",
        "short_entry",
        "atr_value",
        "long_stop",
        "short_stop",
        "bars_since_open",
        "traded_today",
    ]

    def __init__(
        self,
        cta_engine: object,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ) -> None:
        """初始化策略。"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=100)

        self.exit_time: time = time(
            hour=self.exit_hour, minute=self.exit_minute
        )
        self.day_session_start: time = time(hour=9, minute=0)
        self.day_session_end: time = time(hour=15, minute=0)

        self.in_day_session: bool = False
        self.observation_done: bool = False

    def on_init(self) -> None:
        """策略初始化。"""
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self) -> None:
        """策略启动。"""
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """策略停止。"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        """Tick数据更新。"""
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """1分钟K线更新，执行核心策略逻辑。"""
        self.cancel_all()

        self.am.update_bar(bar)
        if not self.am.inited:
            return

        bar_time: time = bar.datetime.time()

        # 检测日盘开盘
        if self.is_day_session_start(bar_time):
            self.range_high = bar.high_price
            self.range_low = bar.low_price
            self.bars_since_open = 0
            self.in_day_session = True
            self.observation_done = False
            self.traded_today = False
            self.long_entry = 0.0
            self.short_entry = 0.0
            self.long_stop = 0.0
            self.short_stop = 0.0

        # 非日盘时段不交易
        if not self.in_day_session:
            self.put_event()
            return

        # 日盘结束标记
        if bar_time >= self.day_session_end:
            self.in_day_session = False
            self.put_event()
            return

        self.bars_since_open += 1
        self.atr_value = self.am.atr(self.atr_window)

        # 观察窗口内：更新区间高低点
        if self.bars_since_open <= self.observation_minutes:
            self.range_high = max(self.range_high, bar.high_price)
            self.range_low = min(self.range_low, bar.low_price)
            self.put_event()
            return

        # 观察窗口结束，计算突破价位
        if not self.observation_done:
            self.observation_done = True
            range_width: float = self.range_high - self.range_low
            self.long_entry = (
                self.range_high + range_width * self.range_multiplier
            )
            self.short_entry = (
                self.range_low - range_width * self.range_multiplier
            )

        # 尾盘平仓
        if bar_time >= self.exit_time:
            if self.pos > 0:
                self.sell(bar.close_price, abs(self.pos))
            elif self.pos < 0:
                self.cover(bar.close_price, abs(self.pos))
            self.put_event()
            return

        # 无持仓：检查突破入场
        if self.pos == 0 and not self.traded_today:
            if bar.close_price > self.long_entry and self.long_entry > 0:
                self.buy(bar.close_price, self.fixed_size)
                self.long_stop = (
                    bar.close_price
                    - self.atr_value * self.atr_stop_multiplier
                )
                self.traded_today = True
            elif bar.close_price < self.short_entry and self.short_entry > 0:
                self.short(bar.close_price, self.fixed_size)
                self.short_stop = (
                    bar.close_price
                    + self.atr_value * self.atr_stop_multiplier
                )
                self.traded_today = True

        # 持仓期间：ATR移动止损
        elif self.pos > 0:
            self.long_stop = max(
                self.long_stop,
                bar.close_price - self.atr_value * self.atr_stop_multiplier,
            )
            if bar.low_price <= self.long_stop:
                self.sell(bar.close_price, abs(self.pos))

        elif self.pos < 0:
            self.short_stop = min(
                self.short_stop,
                bar.close_price + self.atr_value * self.atr_stop_multiplier,
            )
            if bar.high_price >= self.short_stop:
                self.cover(bar.close_price, abs(self.pos))

        self.put_event()

    def is_day_session_start(self, bar_time: time) -> bool:
        """判断是否为日盘开盘第一根K线。"""
        return (
            bar_time >= self.day_session_start
            and bar_time < time(hour=9, minute=1)
            and not self.in_day_session
        )

    def on_order(self, order: OrderData) -> None:
        """委托更新。"""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """成交更新。"""
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """停止单更新。"""
        pass
