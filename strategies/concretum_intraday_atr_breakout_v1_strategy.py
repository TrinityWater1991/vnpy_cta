"""
Concretum Intraday ATR Breakout Strategy (v1)

基线策略：
- 1小时K线（BarGenerator合成），每天开盘后计算 ATR(14)
- 上轨 = 当日开盘价 + atr_multiplier × ATR(14)
- 下轨 = 当日开盘价 - atr_multiplier × ATR(14)
- 价格突破上轨入场做多，突破下轨入场做空
- 价格回归开盘价离场，收盘前强制平仓
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
from vnpy.trader.constant import Interval


class ConcretumIntradayAtrBreakoutV1Strategy(CtaTemplate):
    """Concretum Intraday ATR Breakout v1 — 基线版"""

    author: str = "cta_agent"

    # 策略参数
    atr_period: int = 14
    atr_multiplier: float = 0.5
    fixed_size: int = 1

    # 策略变量
    daily_open: float = 0.0
    upper_channel: float = 0.0
    lower_channel: float = 0.0
    atr_value: float = 0.0
    current_date: str = ""

    parameters: list[str] = [
        "atr_period",
        "atr_multiplier",
        "fixed_size",
    ]

    variables: list[str] = [
        "daily_open",
        "upper_channel",
        "lower_channel",
        "atr_value",
        "current_date",
    ]

    def __init__(
        self,
        cta_engine: object,
        strategy_name: str,
        vt_symbol: str,
        setting: dict,
    ) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bg = BarGenerator(
            self.on_bar,
            window=1,
            on_window_bar=self.on_hour_bar,
            interval=Interval.HOUR,
        )
        self.am = ArrayManager()

    def on_init(self) -> None:
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self) -> None:
        self.write_log("策略启动")

    def on_stop(self) -> None:
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """1分钟K线回调，用于合成小时K线"""
        self.bg.update_bar(bar)

    def on_hour_bar(self, bar: BarData) -> None:
        """1小时K线回调，在此执行策略逻辑"""
        self.cancel_all()

        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # 检测新交易日
        bar_date = bar.datetime.strftime("%Y-%m-%d")
        if bar_date != self.current_date:
            self.current_date = bar_date
            self.daily_open = bar.open_price

            # 如果有隔夜仓位，开盘平仓
            if self.pos != 0:
                if self.pos > 0:
                    self.sell(bar.open_price, abs(self.pos))
                else:
                    self.cover(bar.open_price, abs(self.pos))
                return

        # 计算ATR和通道
        atr_array = self.am.atr(self.atr_period, array=True)
        self.atr_value = atr_array[-1]
        self.upper_channel = self.daily_open + self.atr_multiplier * self.atr_value
        self.lower_channel = self.daily_open - self.atr_multiplier * self.atr_value

        # =====================
        # 平仓逻辑
        # =====================
        if self.pos > 0:
            # 收盘前强制平仓（最后一根1h K线，14:00或22:00）
            if bar.datetime.hour >= 14:
                self.sell(bar.close_price, abs(self.pos))
                return
            if bar.datetime.hour >= 22:
                self.sell(bar.close_price, abs(self.pos))
                return

            # 价格回归开盘价平仓（高低点触及开盘价）
            if bar.low_price <= self.daily_open:
                self.sell(self.daily_open, abs(self.pos))
                return
            return

        if self.pos < 0:
            # 收盘前强制平仓
            if bar.datetime.hour >= 14:
                self.cover(bar.close_price, abs(self.pos))
                return
            if bar.datetime.hour >= 22:
                self.cover(bar.close_price, abs(self.pos))
                return

            # 价格回归开盘价平仓
            if bar.high_price >= self.daily_open:
                self.cover(self.daily_open, abs(self.pos))
                return
            return

        # =====================
        # 入场逻辑（无仓位时）
        # =====================
        if self.am.count < self.atr_period + 5:
            return

        if bar.close_price > self.upper_channel:
            self.buy(bar.close_price, self.fixed_size)
        elif bar.close_price < self.lower_channel:
            self.short(bar.close_price, self.fixed_size)

        self.put_event()

    def on_trade(self, trade: TradeData) -> None:
        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
