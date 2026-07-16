"""
VeighNa策略关键词:
海龟交易法则, 唐奇安通道, 突破策略, 趋势跟踪, ATR止损,
N日高点突破, N日低点突破, 趋势交易系统, 多空双向, 移动止损
"""
from __future__ import annotations

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


class TurtleTradingStrategy(CtaTemplate):
    """
    经典海龟交易策略

    基于原始 Turtle Trading System (1983) 的核心思想：
    1. 唐奇安通道(N日)突破入场
    2. 较短周期(M日)反突破离场
    3. ATR动态止损
    4. 多空双向

    策略核心执行流程:

    1. K线数据更新 (on_bar)
       |
    2. 撤销未成交委托
    3. 更新AM并检查初始化
       |
    4. 计算技术指标(通道、ATR)
       |
    5. 根据持仓状态执行逻辑:
       ├── 无持仓: 挂突破停止单
       ├── 多头持仓: ATR移动止损 + 离场通道
       └── 空头持仓: ATR移动止损 + 离场通道
       |
    6. 推送策略状态更新
    """
    author: str = "Hermes CTA Agent"

    # === 策略参数 ===
    entry_window: int = 10       # 入场通道周期(2h bar)
    exit_window: int = 5         # 离场通道周期(2h bar)-未使用(ATR止损替代)
    atr_window: int = 20         # ATR计算周期
    stop_multiplier: float = 2.0  # ATR止损倍数
    fixed_size: int = 1          # 每次交易数量
    filter_ema_window: int = 20  # EMA趋势过滤周期

    # === 策略变量 ===
    entry_up: float = 0.0        # 入场通道上轨
    entry_down: float = 0.0      # 入场通道下轨
    exit_up: float = 0.0         # 离场通道上轨
    exit_down: float = 0.0       # 离场通道下轨
    atr_value: float = 0.0       # ATR值
    filter_ema: float = 0.0      # EMA趋势过滤值
    long_stop: float = 0.0       # 多头止损价
    short_stop: float = 0.0      # 空头止损价
    long_entry_price: float = 0.0  # 多头入场均价
    short_entry_price: float = 0.0 # 空头入场均价
    intra_trade_high: float = 0.0  # 持仓期间最高价
    intra_trade_low: float = 0.0   # 持仓期间最低价

    parameters: list[str] = [
        "entry_window",
        "exit_window",
        "atr_window",
        "stop_multiplier",
        "fixed_size",
        "filter_ema_window",
    ]

    variables: list[str] = [
        "entry_up",
        "entry_down",
        "exit_up",
        "exit_down",
        "atr_value",
        "long_stop",
        "short_stop",
        "long_entry_price",
        "short_entry_price",
        "intra_trade_high",
        "intra_trade_low",
    ]

    def __init__(self, cta_engine: object, strategy_name: str,
                 vt_symbol: str, setting: dict) -> None:
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.bg: BarGenerator = BarGenerator(
            self.on_bar,
            window=2,
            on_window_bar=self.on_hour_bar,
            interval=Interval.HOUR,
        )
        self.am: ArrayManager = ArrayManager(size=250)

    def on_init(self) -> None:
        """策略初始化"""
        self.write_log("策略初始化")
        self.load_bar(self.entry_window + 10)

    def on_start(self) -> None:
        """策略启动"""
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """策略停止"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        """Tick更新"""
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """1分钟K线更新"""
        self.bg.update_bar(bar)

    def on_hour_bar(self, bar: BarData) -> None:
        """
        目标周期（1h）K线更新回调

        执行流程:
            1. 撤销未成交委托
            2. 更新AM并检查初始化
            3. 计算技术指标
            4. 执行交易逻辑
            5. 推送更新
        """
        # 1. 撤销所有未成交委托
        self.cancel_all()

        # 2. 更新数据
        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # 3. 计算技术指标
        self.calculate_indicators()

        # 4. 交易逻辑
        if self.pos == 0:
            self.handle_no_position(bar)
        elif self.pos > 0:
            self.update_long_position(bar)
        elif self.pos < 0:
            self.update_short_position(bar)

        # 5. 推送更新
        self.put_event()

    def calculate_indicators(self) -> None:
        """集中计算所有技术指标"""
        self.entry_up, self.entry_down = self.am.donchian(self.entry_window)
        self.exit_up, self.exit_down = self.am.donchian(self.exit_window)
        self.atr_value = self.am.atr(self.atr_window)
        self.filter_ema = self.am.ema(self.filter_ema_window)

    def handle_no_position(self, bar: BarData) -> None:
        """
        空仓时的入场逻辑

        带EMA方向过滤：
        - 价格在EMA上方时，只做多（挂买入停止单）
        - 价格在EMA下方时，只做空（挂卖出停止单）
        """
        # 重置追踪变量
        self.long_stop = 0.0
        self.short_stop = 0.0
        self.intra_trade_high = bar.high_price
        self.intra_trade_low = bar.low_price

        # EMA方向过滤：收盘价在EMA上方只做多，下方只做空
        above_ema = bar.close_price > self.filter_ema

        if above_ema:
            # 只做多
            self.buy(self.entry_up, self.fixed_size, True)
        else:
            # 只做空
            self.short(self.entry_down, self.fixed_size, True)

    def update_long_position(self, bar: BarData) -> None:
        """
        多头持仓管理

        离场条件（任一触发即平仓）：
        1. 价格跌破离场通道下轨
        2. ATR移动止损触发
        """
        # 更新持仓期间最高价
        self.intra_trade_high = max(self.intra_trade_high, bar.high_price)

        # ATR移动止损（纯ATR止损，去掉反突破离场）
        self.long_stop = self.intra_trade_high - self.atr_value * self.stop_multiplier
        self.sell(self.long_stop, abs(self.pos), True)

    def update_short_position(self, bar: BarData) -> None:
        """
        空头持仓管理

        离场条件（任一触发即平仓）：
        1. 价格突破离场通道上轨
        2. ATR移动止损触发
        """
        # 更新持仓期间最低价
        self.intra_trade_low = min(self.intra_trade_low, bar.low_price)

        # ATR移动止损（纯ATR止损，去掉反突破离场）
        self.short_stop = self.intra_trade_low + self.atr_value * self.stop_multiplier
        self.cover(self.short_stop, abs(self.pos), True)

    def on_trade(self, trade: TradeData) -> None:
        """成交回调：记录入场价格"""
        if trade.direction.value == "多":
            self.long_entry_price = trade.price
        elif trade.direction.value == "空":
            self.short_entry_price = trade.price

    def on_order(self, order: OrderData) -> None:
        """订单状态回调（暂不处理）"""
        pass

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """停止单状态回调（暂不处理）"""
        pass
