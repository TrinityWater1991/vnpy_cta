"""
Smash Day 反转策略 v2 — 日频信号 + 停止单入场。

从 1m 数据合成 1h K线，在 1h K线上检测日级别变化，
在交易日结束时检测 Smash Day 模式，下一交易日开盘用停止单入场。

Smash Day:
- Buy: 当日收盘 < 前日最低 AND 当日最低 < 回顾期最低 → 下一日突破今日最高做多
- Sell: 当日收盘 > 前日最高 AND 当日最高 > 回顾期最高 → 下一日跌破今日最低做空
"""
from __future__ import annotations

from typing import Any
from datetime import date

from vnpy.trader.object import BarData, TickData, OrderData, TradeData
from vnpy_ctastrategy import (
    CtaTemplate,
    BarGenerator,
    StopOrder,
)


class SmashDayStrategy(CtaTemplate):
    """Smash Day 反转策略 — 日频信号 + 停止单入场。"""

    author = "cta_agent"

    # 参数
    smash_lookback: int = 16          # Smash Day 回顾期（交易日数）
    atr_window: int = 20              # ATR 窗口
    atr_multiplier: float = 2.0       # ATR 止损倍数
    fixed_size: int = 1               # 固定手数

    # 变量
    atr_value: float = 0.0
    long_stop: float = 0.0
    short_stop: float = 0.0
    current_direction: int = 0
    last_signal: str = ""

    parameters = [
        "smash_lookback",
        "atr_window",
        "atr_multiplier",
        "fixed_size",
    ]
    variables = [
        "atr_value",
        "long_stop",
        "short_stop",
        "current_direction",
        "last_signal",
    ]

    def __init__(self, cta_engine: Any, strategy_name: str,
                 vt_symbol: str, setting: dict[str, Any]) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bg = BarGenerator(self.on_bar, 60, self.on_60min_bar)

        self._day_open: float = 0.0
        self._day_high: float = 0.0
        self._day_low: float = 1e10
        self._day_close: float = 0.0
        self._prev_date: date | None = None

        self._highs: list[float] = []
        self._lows: list[float] = []
        self._closes: list[float] = []

        self._buy_trigger: float = 0.0
        self._sell_trigger: float = 0.0

        self._trade_high: float = 0.0
        self._trade_low: float = 1e10
        self._hourly_closes: list[float] = []

    def on_init(self) -> None:
        self.write_log("策略初始化")
        self.load_bar(60)

    def on_start(self) -> None:
        self.write_log("策略启动")

    def on_stop(self) -> None:
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        self.bg.update_bar(bar)

    def on_60min_bar(self, bar: BarData) -> None:
        self.cancel_all()
        bar_date = bar.datetime.date()

        # ATR
        self._hourly_closes.append(bar.close_price)
        if len(self._hourly_closes) > self.atr_window + 5:
            self._hourly_closes = self._hourly_closes[-(self.atr_window + 5):]
        if len(self._hourly_closes) >= self.atr_window + 1:
            diffs = []
            for i in range(1, min(len(self._hourly_closes), self.atr_window + 1)):
                diffs.append(abs(self._hourly_closes[-i] - self._hourly_closes[-i - 1]))
            self.atr_value = sum(diffs) / len(diffs)

        is_new_day = self._prev_date is not None and bar_date != self._prev_date

        if is_new_day:
            self._handle_completed_day()
            self._try_entry(bar)
        elif self._prev_date is None:
            self._reset_day(bar)

        if self._day_open == 0.0:
            self._reset_day(bar)

        self._day_high = max(self._day_high, bar.high_price)
        self._day_low = min(self._day_low, bar.low_price)
        self._day_close = bar.close_price
        self._prev_date = bar_date

        self._manage_stops(bar)
        self.put_event()

    def _reset_day(self, bar: BarData) -> None:
        self._day_open = bar.open_price
        self._day_high = bar.high_price
        self._day_low = bar.low_price
        self._day_close = bar.close_price

    def _handle_completed_day(self) -> None:
        self._highs.append(self._day_high)
        self._lows.append(self._day_low)
        self._closes.append(self._day_close)

        max_cache = max(self.smash_lookback + 5, 30)
        if len(self._highs) > max_cache:
            self._highs = self._highs[-max_cache:]
            self._lows = self._lows[-max_cache:]
            self._closes = self._closes[-max_cache:]

        self._detect_smash_day()

        self._day_open = 0.0
        self._day_high = 0.0
        self._day_low = 1e10
        self._day_close = 0.0

    def _detect_smash_day(self) -> None:
        if len(self._closes) < self.smash_lookback + 2:
            return

        c = self._closes[-1]
        h = self._highs[-1]
        l = self._lows[-1]
        prev_high = self._highs[-2] if len(self._highs) >= 2 else 0.0
        prev_low = self._lows[-2] if len(self._lows) >= 2 else 0.0
        lb_low = min(self._lows[-(self.smash_lookback + 1):-1])
        lb_high = max(self._highs[-(self.smash_lookback + 1):-1])

        if (c < prev_low) and (l < lb_low):
            self._buy_trigger = h
            self._sell_trigger = 0.0
            self.last_signal = f"SmashBuy(h={h:.1f})"
        elif (c > prev_high) and (h > lb_high):
            self._sell_trigger = l
            self._buy_trigger = 0.0
            self.last_signal = f"SmashSell(l={l:.1f})"

    def _try_entry(self, bar: BarData) -> None:
        if self._buy_trigger == 0.0 and self._sell_trigger == 0.0:
            return

        if self._buy_trigger > 0:
            if self.pos < 0:
                self.cover(bar.close_price * 1.01, abs(self.pos))
            if self.pos <= 0:
                self.buy(self._buy_trigger, self.fixed_size, True)
                self.current_direction = 1

        if self._sell_trigger > 0:
            if self.pos > 0:
                self.sell(bar.close_price * 0.99, abs(self.pos))
            if self.pos >= 0:
                self.short(self._sell_trigger, self.fixed_size, True)
                self.current_direction = -1

        self._buy_trigger = 0.0
        self._sell_trigger = 0.0

    def _manage_stops(self, bar: BarData) -> None:
        if self.pos > 0:
            self._trade_high = max(self._trade_high, bar.high_price)
            self.long_stop = self._trade_high - self.atr_value * self.atr_multiplier
            if self.long_stop > 0 and bar.close_price <= self.long_stop:
                self.sell(bar.close_price * 0.99, abs(self.pos))
                self._reset_state()
        elif self.pos < 0:
            self._trade_low = min(self._trade_low, bar.low_price)
            self.short_stop = self._trade_low + self.atr_value * self.atr_multiplier
            if self.short_stop > 0 and bar.close_price >= self.short_stop:
                self.cover(bar.close_price * 1.01, abs(self.pos))
                self._reset_state()

    def _reset_state(self) -> None:
        self._trade_high = 0.0
        self._trade_low = 1e10
        self.long_stop = 0.0
        self.short_stop = 0.0

    def on_trade(self, trade: TradeData) -> None:
        if self.pos == 0:
            self.current_direction = 0
            self._reset_state()
        elif self.pos > 0:
            self._trade_high = trade.price
        elif self.pos < 0:
            self._trade_low = trade.price
        self.put_event()

    def on_order(self, order: OrderData) -> None:
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        pass
