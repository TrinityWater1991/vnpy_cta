"""
双通道趋势过滤策略 v2b — Donchian + EMA 斜率过滤（停止单版）

方向2改进版：使用停止单（stop=True）捕获盘中通道突破。
- EMA 上升趋势中，挂买入停止单在 Donchian 上轨
- EMA 下降趋势中，挂卖出停止单在 Donchian 下轨
- cancel_all() 每根K线都会撤销未成交的挂单，所以重新挂
"""
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
from vnpy.trader.constant import Interval


class ConcretumDualChannelV2bStrategy(CtaTemplate):
    """双通道趋势过滤 v2b — Donchian + EMA 斜率（停止单版）。"""

    author: str = "cta_agent"

    # 策略参数
    entry_window: int = 40
    exit_window: int = 20
    ema_window: int = 20
    atr_window: int = 20
    atr_stop_multiplier: float = 3.0
    fixed_size: int = 1

    # 策略变量
    donchian_up: float = 0.0
    donchian_down: float = 0.0
    exit_up: float = 0.0
    exit_down: float = 0.0
    ema_value: float = 0.0
    prev_ema: float = 0.0
    ema_slope_up: bool = False
    atr_value: float = 0.0
    intra_trade_high: float = 0.0
    intra_trade_low: float = 0.0
    long_stop: float = 0.0
    short_stop: float = 0.0

    parameters: list[str] = [
        "entry_window",
        "exit_window",
        "ema_window",
        "atr_window",
        "atr_stop_multiplier",
        "fixed_size",
    ]

    variables: list[str] = [
        "donchian_up",
        "donchian_down",
        "exit_up",
        "exit_down",
        "ema_value",
        "ema_slope_up",
        "atr_value",
        "intra_trade_high",
        "intra_trade_low",
        "long_stop",
        "short_stop",
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

        self.bg = BarGenerator(
            self.on_bar,
            window=2,
            on_window_bar=self.on_hour_bar,
            interval=Interval.HOUR,
        )
        self.am = ArrayManager(size=250)

    def on_init(self) -> None:
        """策略初始化。"""
        self.write_log("策略初始化")
        self.load_bar(30)

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
        """1分钟K线更新。"""
        self.bg.update_bar(bar)

    def on_hour_bar(self, bar: BarData) -> None:
        """1小时K线更新。"""
        self.cancel_all()

        self.am.update_bar(bar)
        if not self.am.inited:
            return

        self.calculate_indicators(bar)

        if self.pos == 0:
            self.handle_no_position(bar)
        elif self.pos > 0:
            self.update_long_position(bar)
        elif self.pos < 0:
            self.update_short_position(bar)

        self.put_event()

    def calculate_indicators(self, bar: BarData) -> None:
        """集中计算所有技术指标。"""
        self.donchian_up, self.donchian_down = self.am.donchian(
            self.entry_window
        )
        self.exit_up, self.exit_down = self.am.donchian(self.exit_window)
        self.atr_value = self.am.atr(self.atr_window)
        self.prev_ema = self.ema_value
        self.ema_value = self.am.ema(self.ema_window)
        self.ema_slope_up = self.ema_value > self.prev_ema

    def handle_no_position(self, bar: BarData) -> None:
        """空仓时挂停止单入场。"""
        self.intra_trade_high = bar.high_price
        self.intra_trade_low = bar.low_price

        # EMA上升趋势：在 Donchian 上轨挂买入停止单
        if self.ema_slope_up and self.donchian_up > bar.close_price:
            self.buy(self.donchian_up, self.fixed_size, stop=True)

        # EMA下降趋势：在 Donchian 下轨挂卖出停止单
        elif not self.ema_slope_up and self.donchian_down < bar.close_price:
            self.short(self.donchian_down, self.fixed_size, stop=True)

    def update_long_position(self, bar: BarData) -> None:
        """多头持仓管理。"""
        self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
        stop_price: float = (
            self.intra_trade_high
            - self.atr_value * self.atr_stop_multiplier
        )
        self.long_stop = max(self.long_stop, stop_price)
        sell_price: float = max(self.long_stop, self.exit_down)
        self.sell(sell_price, abs(self.pos), stop=True)

    def update_short_position(self, bar: BarData) -> None:
        """空头持仓管理。"""
        self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
        stop_price: float = (
            self.intra_trade_low
            + self.atr_value * self.atr_stop_multiplier
        )
        self.short_stop = min(self.short_stop, stop_price)
        cover_price: float = min(self.short_stop, self.exit_up)
        self.cover(cover_price, abs(self.pos), stop=True)

    def on_order(self, order: OrderData) -> None:
        """委托更新。"""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """成交更新。"""
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """停止单更新。"""
        pass
