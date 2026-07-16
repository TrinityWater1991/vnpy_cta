"""
多周期MA趋势因子策略（MultiMaTrendStrategy）

基于Han, Zhou, Zhu (2016) "A Trend Factor"论文思路：
- 计算多个周期的MA，归一化为 (MA - Price) / Price
- 等权组合所有MA信号得到趋势因子
- 趋势因子穿越阈值入场，回归零轴离场
- ATR移动止损保护

适配：rb99.SHFE 1小时K线
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


class MultiMaTrendStrategy(CtaTemplate):
    """
    多周期MA趋势因子策略。

    用5个周期的MA归一化信号等权求和，
    形成综合趋势因子，穿越阈值时交易。
    """

    author: str = "cta_agent"

    # 策略参数
    ma_short: int = 10
    ma_mid1: int = 20
    ma_mid2: int = 50
    ma_long1: int = 100
    ma_long2: int = 200
    entry_threshold: float = 0.008
    exit_threshold: float = 0.0
    atr_window: int = 20
    atr_stop_multiplier: float = 5.0
    fixed_size: int = 1

    # 策略变量
    trend_factor: float = 0.0
    prev_trend_factor: float = 0.0
    atr_value: float = 0.0
    intra_trade_high: float = 0.0
    intra_trade_low: float = 0.0
    long_stop: float = 0.0
    short_stop: float = 0.0

    parameters: list[str] = [
        "ma_short",
        "ma_mid1",
        "ma_mid2",
        "ma_long1",
        "ma_long2",
        "entry_threshold",
        "exit_threshold",
        "atr_window",
        "atr_stop_multiplier",
        "fixed_size",
    ]

    variables: list[str] = [
        "trend_factor",
        "prev_trend_factor",
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
            window=1,
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
        """1小时K线更新，执行核心策略逻辑。"""
        self.cancel_all()

        self.am.update_bar(bar)
        if not self.am.inited:
            return

        close: float = bar.close_price
        if close == 0.0:
            return

        # 计算多周期MA归一化信号并等权求和
        ma_periods: list[int] = [
            self.ma_short, self.ma_mid1, self.ma_mid2,
            self.ma_long1, self.ma_long2,
        ]

        signal_sum: float = 0.0
        for period in ma_periods:
            ma_val: float = self.am.sma(period)
            # 归一化：(MA - Price) / Price，MA > Price为正（价格在MA下方=下跌趋势）
            # 反转符号：Price > MA为正信号（上升趋势）
            signal_sum += (close - ma_val) / close

        self.prev_trend_factor = self.trend_factor
        self.trend_factor = signal_sum / len(ma_periods)

        # ATR
        self.atr_value = self.am.atr(self.atr_window)

        # 交易逻辑：基于趋势因子状态改变
        if self.pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            # 趋势因子上穿entry_threshold做多
            if (self.trend_factor > self.entry_threshold
                    and self.prev_trend_factor <= self.entry_threshold):
                self.buy(bar.close_price, self.fixed_size)
            # 趋势因子下穿-entry_threshold做空
            elif (self.trend_factor < -self.entry_threshold
                  and self.prev_trend_factor >= -self.entry_threshold):
                self.short(bar.close_price, self.fixed_size)

        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.long_stop = (
                self.intra_trade_high
                - self.atr_value * self.atr_stop_multiplier
            )

            # 趋势因子回归exit_threshold以下离场
            if self.trend_factor < self.exit_threshold:
                self.sell(bar.close_price, abs(self.pos))
            else:
                self.sell(self.long_stop, abs(self.pos), stop=True)

        elif self.pos < 0:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            self.short_stop = (
                self.intra_trade_low
                + self.atr_value * self.atr_stop_multiplier
            )

            # 趋势因子回归-exit_threshold以上离场
            if self.trend_factor > -self.exit_threshold:
                self.cover(bar.close_price, abs(self.pos))
            else:
                self.cover(self.short_stop, abs(self.pos), stop=True)

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        """委托更新。"""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """成交更新。"""
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """停止单更新。"""
        pass
