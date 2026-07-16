"""
双均线 CTA 策略，支持 10 种均线类型。

金叉做多，死叉做空，永持反手模式。
ArrayManager size=150，信号在 bar 收盘判定，次根 bar 成交。
"""

from typing import Optional

import numpy as np
import talib

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


# ── MA 类型常量 ────────────────────────────────────────
MA_TYPE_TALIB: dict[str, int] = {
    "SMA": 0,
    "EMA": 1,
    "WMA": 2,
    "DEMA": 3,
    "TEMA": 4,
    "TRIMA": 5,
    "KAMA": 6,
    "T3": 8,
}
"""TA-Lib MA 函数的 matype 参数映射"""

# HMA 和 VWMA 为自定义实现，不在 TA-Lib 的 MA 函数中


def compute_hma(close: np.ndarray, n: int) -> np.ndarray:
    """Hull Moving Average：WMA(sqrt(n)) of (2 * WMA(n/2) - WMA(n))"""
    if n < 2:
        return close
    half_n: int = max(1, n // 2)
    sqrt_n: int = max(1, int(np.sqrt(n)))

    wma_half: np.ndarray = talib.WMA(close, half_n)
    wma_full: np.ndarray = talib.WMA(close, n)
    raw: np.ndarray = 2.0 * wma_half - wma_full
    return talib.WMA(raw, sqrt_n)


def compute_vwma(close: np.ndarray, volume: np.ndarray, n: int) -> np.ndarray:
    """Volume Weighted Moving Average：Σ(price × vol) / Σ(vol) 滚动窗口"""
    if n < 1:
        return close
    # 用卷积实现滚动求和
    price_vol: np.ndarray = close * volume
    sum_pv: np.ndarray = np.convolve(price_vol, np.ones(n), mode="same")
    sum_v: np.ndarray = np.convolve(volume, np.ones(n), mode="same")
    result: np.ndarray = np.full_like(close, np.nan)
    mask: np.ndarray = sum_v > 0
    result[mask] = sum_pv[mask] / sum_v[mask]
    # 前 n-1 个位置回退到累积均值
    for i in range(n - 1):
        if i < len(result):
            cum_v: float = float(np.sum(volume[max(0, i - n + 1) : i + 1]))
            if cum_v > 0:
                result[i] = np.sum(price_vol[max(0, i - n + 1) : i + 1]) / cum_v
    return result


# ── 策略类 ──────────────────────────────────────────────


class DualMaStrategy(CtaTemplate):
    """双均线 CTA 策略，金叉做多，死叉做空"""

    author: str = "Harness"

    # 参数（外部可调）
    ma_type: str = "EMA"
    fast_window: int = 10
    slow_window: int = 70
    fixed_size: int = 1

    # 变量（内部计算，UI 只读）
    fast_ma_value: float = 0.0
    slow_ma_value: float = 0.0

    parameters: list[str] = [
        "ma_type",
        "fast_window",
        "slow_window",
        "fixed_size",
    ]
    variables: list[str] = [
        "fast_ma_value",
        "slow_ma_value",
    ]

    # 内部状态
    last_fast_ma: float = 0.0
    last_slow_ma: float = 0.0
    first_bar: bool = True

    def __init__(
        self, cta_engine, strategy_name: str, vt_symbol: str, setting: dict
    ) -> None:
        """初始化策略实例"""
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)

    def on_init(self) -> None:
        """策略初始化回调：创建 K 线合成器与指标缓存容器"""
        self.write_log("策略初始化")

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=150)

        self.last_fast_ma = 0.0
        self.last_slow_ma = 0.0
        self.first_bar = True

        self.load_bar(150)

    def on_start(self) -> None:
        """策略启动回调"""
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """策略停止回调"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        """Tick 数据推送回调"""
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """K 线数据推送回调"""
        # 1. 撤销之前所有未成交委托
        self.cancel_all()

        # 2. 更新 ArrayManager
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # 3. 计算快慢均线值
        fast_val: float = self._calc_ma(self.fast_window)
        slow_val: float = self._calc_ma(self.slow_window)

        self.fast_ma_value = fast_val
        self.slow_ma_value = slow_val

        # 4. 跳过首根 bar（无前值做穿越判定）
        if self.first_bar:
            self.last_fast_ma = fast_val
            self.last_slow_ma = slow_val
            self.first_bar = False
            self.put_event()
            return

        # 5. 穿越判定
        cross_up: bool = (
            fast_val > slow_val and self.last_fast_ma <= self.last_slow_ma
        )
        cross_down: bool = (
            fast_val < slow_val and self.last_fast_ma >= self.last_slow_ma
        )

        # 6. 执行交易
        if cross_up and self.pos <= 0:
            if self.pos < 0:
                self.cover(bar.close_price, abs(self.pos))
            self.buy(bar.close_price, self.fixed_size)
        elif cross_down and self.pos >= 0:
            if self.pos > 0:
                self.sell(bar.close_price, abs(self.pos))
            self.short(bar.close_price, self.fixed_size)

        # 7. 保存本根均线值供下一根穿越判定
        self.last_fast_ma = fast_val
        self.last_slow_ma = slow_val

        self.put_event()

    # ── 均线计算分发 ────────────────────────────────────

    def _calc_ma(self, window: int) -> float:
        """根据 self.ma_type 计算指定窗口的均线最新值"""
        close: np.ndarray = self.am.close
        ma_type: str = self.ma_type

        if ma_type in MA_TYPE_TALIB:
            matype: int = MA_TYPE_TALIB[ma_type]
            result: np.ndarray = talib.MA(close, window, matype=matype)
        elif ma_type == "HMA":
            result = compute_hma(close, window)
        elif ma_type == "VWMA":
            volume: np.ndarray = self.am.volume
            result = compute_vwma(close, volume, window)
        else:
            # 未知类型回退到 SMA
            result = talib.SMA(close, window)

        # 取最新值，处理 NaN
        val: float = float(result[-1])
        if np.isnan(val):
            # 回退：用最近的有效值
            valid: np.ndarray = result[~np.isnan(result)]
            val = float(valid[-1]) if len(valid) > 0 else float(close[-1])
        return val

    # ── 回调（空实现）────────────────────────────────────

    def on_order(self, order: OrderData) -> None:
        """委托更新回调"""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """成交更新回调"""
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """停止单更新回调"""
        pass
