#!/usr/bin/env python3
"""TrendStateMachine -- 趋势状态机策略。

核心思路（来自 Royal Purple Dual Asset Trend Follower）：
  趋势是一种状态而非信号事件。三层EMA（Fast/Slow/Regime）确认趋势状态，
  自适应移动止损，被止损后若趋势仍存则重入场。

关键假设验证：
  - 预验证显示三层EMA趋势状态在1hK线上对未来24h方向预测acc≈53%
  - 趋势跟踪本质是低胜率高盈亏比策略，方向预测只是起点
  - 利润来源：止损管理和重入场机制

版本: v1 -- 基础三层EMA趋势状态机 + ATR移动止损 + 重入场

修复日志:
  v1.1: 去掉stop=True参数，改用限价单入场/离场；添加debug日志
"""
from __future__ import annotations

from typing import Any

import numpy as np
from vnpy.trader.object import BarData, TickData, OrderData, TradeData
from vnpy_ctastrategy import (
    CtaTemplate,
    BarGenerator,
    ArrayManager,
)


class TrendStateMachineStrategy(CtaTemplate):
    """趋势状态机策略 v1.1.

    使用三层EMA（Fast/Slow/Regime）判断趋势状态，当趋势状态为bullish时做多，
    bearish时做空。使用ATR自适应移动止损，被止损后若趋势依然存在则重入场。

    参数:
        fast_ema: 快线EMA周期 (默认: 8)
        slow_ema: 慢线EMA周期 (默认: 21)
        regime_ema: 趋势周期EMA (默认: 55)
        atr_period: ATR计算周期 (默认: 14)
        atr_multiplier: ATR倍数用于止损 (默认: 3.0)
        min_hold_bars: 最小持仓K线数 (默认: 2)
        reentry_cooldown: 重入场冷却K线数 (默认: 1)
        hourly_window: 合成1小时K线的1分钟K线数 (默认: 60)
    """
    author = "CTA Agent"

    # 参数
    fast_ema: int = 8
    slow_ema: int = 21
    regime_ema: int = 55
    atr_period: int = 14
    atr_multiplier: float = 3.0
    min_hold_bars: int = 2
    reentry_cooldown: int = 1

    # 变量
    trend_state: int = 0  # 1=bullish, -1=bearish, 0=neutral
    atr_value: float = 0.0
    stop_price: float = 0.0
    bars_since_entry: int = 0
    bars_since_exit: int = 0
    last_trend_state: int = 0

    parameters = [
        "fast_ema", "slow_ema", "regime_ema",
        "atr_period", "atr_multiplier",
        "min_hold_bars", "reentry_cooldown",
    ]
    variables = [
        "trend_state", "atr_value", "stop_price",
        "bars_since_entry", "bars_since_exit",
    ]

    def __init__(self, cta_engine: Any, strategy_name: str,
                 vt_symbol: str, setting: dict[str, Any]) -> None:
        """初始化策略."""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

        # 1分钟K线 -> 1小时K线（窗口60分钟合成）
        self.bg: BarGenerator = BarGenerator(self.on_bar, 60, self.on_hourly_bar)
        # 用ArrayManager管理1小时K线数据
        self.am: ArrayManager = ArrayManager(size=100)

        # 状态追踪
        self._entry_bar_index: int = 0
        self._exit_bar_index: int = 0
        self._bar_count: int = 0
        self._hourly_ema_fast: float = 0.0
        self._hourly_ema_slow: float = 0.0
        self._hourly_ema_regime: float = 0.0

        # 重入场防抖
        self._last_exit_trend_state: int = 0

    def on_init(self) -> None:
        """策略初始化回调."""
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self) -> None:
        """策略启动回调."""
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """策略停止回调."""
        self.write_log("策略停止")

    def on_bar(self, bar: BarData) -> None:
        """1分钟K线回调."""
        self.bg.update_bar(bar)

    def on_hourly_bar(self, bar: BarData) -> None:
        """1小时K线回调 -- 主逻辑入口."""
        self.write_log(f"[DEBUG] hourly_bar: {bar.datetime} close={bar.close_price} pos={self.pos}")
        self._bar_count += 1
        self.bars_since_entry += 1
        self.bars_since_exit += 1

        # 更新ArrayManager
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # ---- 1. 计算指标 ----
        ema_fast: np.ndarray = self.am.ema(self.fast_ema, array=True)
        ema_slow: np.ndarray = self.am.ema(self.slow_ema, array=True)
        ema_regime: np.ndarray = self.am.ema(self.regime_ema, array=True)
        atr_array: np.ndarray = self.am.atr(self.atr_period, array=True)

        current_fast: float = ema_fast[-1]
        current_slow: float = ema_slow[-1]
        current_regime: float = ema_regime[-1]
        self.atr_value = float(atr_array[-1])
        current_close: float = bar.close_price

        # 保存用于调试
        self._hourly_ema_fast = current_fast
        self._hourly_ema_slow = current_slow
        self._hourly_ema_regime = current_regime

        # ---- 2. 判断趋势状态 ----
        prev_trend: int = self.trend_state
        if current_fast > current_slow and current_slow > current_regime:
            self.trend_state = 1  # bullish
        elif current_fast < current_slow and current_slow < current_regime:
            self.trend_state = -1  # bearish
        else:
            self.trend_state = 0  # neutral

        # ---- 3. 状态机逻辑 ----
        # 趋势状态发生变化时更新记录
        if prev_trend != self.trend_state:
            self.last_trend_state = prev_trend

        # 如果不在冷却期且趋势状态明确
        can_reenter: bool = (
            self.bars_since_exit >= self.reentry_cooldown
        )

        # ---- 入场逻辑 ----
        if self.pos == 0:
            self.stop_price = 0.0

            if self.trend_state == 1 and can_reenter:
                self.write_log(f"[DEBUG] 做多条件满足 close={current_close:.1f}")
                # 做多: 以当前收盘价限价入场
                self.buy(bar.close_price, 1)
                self._entry_bar_index = self._bar_count
                self.bars_since_entry = 0
                self.stop_price = current_close - self.atr_multiplier * self.atr_value
                self.write_log(
                    f"做多入场 price={bar.close_price:.1f} "
                    f"trend_state=bullish "
                    f"stop={self.stop_price:.1f}"
                )

            elif self.trend_state == -1 and can_reenter:
                self.write_log(f"[DEBUG] 做空条件满足 close={current_close:.1f}")
                # 做空: 以当前收盘价限价入场
                self.short(bar.close_price, 1)
                self._entry_bar_index = self._bar_count
                self.bars_since_entry = 0
                self.stop_price = current_close + self.atr_multiplier * self.atr_value
                self.write_log(
                    f"做空入场 price={bar.close_price:.1f} "
                    f"trend_state=bearish "
                    f"stop={self.stop_price:.1f}"
                )

        # ---- 持仓管理 (多头) ----
        elif self.pos > 0:
            # 更新止损为追踪止损
            new_stop_long: float = current_close - self.atr_multiplier * self.atr_value
            self.stop_price = max(self.stop_price, new_stop_long) if self.stop_price > 0 else new_stop_long

            # 检查止损
            if bar.low_price <= self.stop_price and self.bars_since_entry >= self.min_hold_bars:
                self.sell(bar.close_price, abs(self.pos))
                self._exit_bar_index = self._bar_count
                self.bars_since_exit = 0
                self._last_exit_trend_state = self.trend_state
                self.write_log(
                    f"多头止损 exit_price={self.stop_price:.1f} "
                    f"trend_state={self.trend_state}"
                )
            # 趋势反转离场
            elif self.trend_state == -1 and self.bars_since_entry >= self.min_hold_bars:
                self.sell(bar.close_price, abs(self.pos))
                self._exit_bar_index = self._bar_count
                self.bars_since_exit = 0
                self._last_exit_trend_state = self.trend_state
                self.write_log(
                    f"多头反手离场 price={bar.close_price:.1f} "
                    f"trend_state=bearish"
                )

        # ---- 持仓管理 (空头) ----
        elif self.pos < 0:
            # 更新止损
            new_stop_short: float = current_close + self.atr_multiplier * self.atr_value
            if self.stop_price > 0:
                self.stop_price = min(self.stop_price, new_stop_short)
            else:
                self.stop_price = new_stop_short

            # 检查止损
            if bar.high_price >= self.stop_price and self.bars_since_entry >= self.min_hold_bars:
                self.cover(bar.close_price, abs(self.pos))
                self._exit_bar_index = self._bar_count
                self.bars_since_exit = 0
                self._last_exit_trend_state = self.trend_state
                self.write_log(
                    f"空头止损 exit_price={self.stop_price:.1f} "
                    f"trend_state={self.trend_state}"
                )
            # 趋势反转离场
            elif self.trend_state == 1 and self.bars_since_entry >= self.min_hold_bars:
                self.cover(bar.close_price, abs(self.pos))
                self._exit_bar_index = self._bar_count
                self.bars_since_exit = 0
                self._last_exit_trend_state = self.trend_state
                self.write_log(
                    f"空头反手离场 price={bar.close_price:.1f} "
                    f"trend_state=bullish"
                )

        # 更新UI显示
        self.put_event()

    def on_tick(self, tick: TickData) -> None:
        """Tick回调 -- 用于BarGenerator."""
        self.bg.update_tick(tick)

    def on_order(self, order: OrderData) -> None:
        """订单回调."""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """成交回调."""
        self.put_event()

    def on_stop_order(self, stop_order: dict) -> None:
        """停止单回调."""
        pass
