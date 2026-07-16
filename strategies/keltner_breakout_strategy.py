"""Keltner Channel 突破策略（1h K线）。

入场：价格突破 Keltner 通道上轨/下轨
离场：价格回归 EMA 中轨

来源：PyQuantLab Keltner Channel Breakout 策略
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


class KeltnerBreakoutStrategy(CtaTemplate):
    """Keltner 通道突破策略（1h K线）"""

    author = "research"

    # 策略参数
    ema_period = 50       # Keltner 通道 EMA 周期
    atr_period = 14       # ATR 周期
    atr_multiplier = 2.0  # ATR 倍数（通道宽度）
    fixed_size = 1        # 固定交易手数

    # 策略变量
    keltner_upper = 0.0
    keltner_lower = 0.0
    keltner_mid = 0.0

    parameters = ["ema_period", "atr_period", "atr_multiplier", "fixed_size"]
    variables = ["keltner_upper", "keltner_lower", "keltner_mid"]

    def __init__(
        self,
        cta_engine,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 从 1m 合成 1h K线
        self.bg = BarGenerator(
            self.on_bar,
            window=1,
            on_window_bar=self.on_hour_bar,
            interval=Interval.HOUR,
        )

        self.am = ArrayManager(size=100)

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self) -> None:
        """策略启动"""
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """策略停止"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        """Tick 数据更新"""
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """K线数据更新（收到 1m 数据，转发给 1h 合成器）"""
        self.bg.update_bar(bar)

    def on_hour_bar(self, bar: BarData) -> None:
        """1h K线数据更新 - 策略主逻辑"""
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # 计算 Keltner 通道（返回上轨和下轨，中轨为 EMA）
        upper, lower = am.keltner(self.ema_period, self.atr_multiplier)
        mid = am.ema(self.ema_period)

        self.keltner_upper = upper
        self.keltner_lower = lower
        self.keltner_mid = mid

        # 入场逻辑：价格突破通道
        if not self.pos:
            # 做多：收盘价上穿上轨
            if bar.close_price > upper:
                self.buy(bar.close_price + 5, self.fixed_size)
            # 做空：收盘价下穿下轨
            elif bar.close_price < lower:
                self.short(bar.close_price - 5, self.fixed_size)

        # 离场逻辑：价格回归 EMA 中轨
        elif self.pos > 0:
            if bar.close_price < mid:
                self.sell(bar.close_price - 5, abs(self.pos))
        elif self.pos < 0:
            if bar.close_price > mid:
                self.cover(bar.close_price + 5, abs(self.pos))

        self.put_event()

    def on_order(self, order: OrderData) -> None:
        """订单更新"""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """成交更新"""
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """停止单更新"""
        pass
