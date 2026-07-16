from typing import Optional

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


class SurgeStrategy(CtaTemplate):
    """基于日内区间突破与RSI的示例策略"""

    author: str = "用Python的交易员"

    # ===== 策略参数 =====
    k1: float = 0.15                    # 多头突破系数
    k2: float = 0.25                    # 空头突破系数
    rsi_window: int = 30                # RSI 计算周期
    rsi_signal: int = 10                # RSI 信号触发阈值
    trailing_long: float = 0.8          # 多头移动止损(百分比)
    trailing_short: float = 1.4         # 空头移动止损(百分比)
    fixed_size: int = 1                 # 每次固定开仓手数
    daily_limit: int = 5                # 每日最大交易次数(仅原逻辑)

    # ===== 策略变量 =====
    day_open: float = 0.0
    day_high: float = 0.0
    day_low: float = 0.0
    day_range: float = 0.0
    long_entry: float = 0.0
    short_entry: float = 0.0
    intra_trade_high: float = 0.0
    intra_trade_low: float = 0.0
    daily_count: int = 0

    # 保存上一根Bar(用于跨日判断)
    last_bar: Optional[BarData] = None

    # ===== 界面显示参数与变量 =====
    parameters = [
        "k1",
        "k2",
        "rsi_window",
        "rsi_signal",
        "trailing_long",
        "trailing_short",
        "fixed_size"
    ]
    variables = [
        "day_range",
        "long_entry",
        "short_entry"
    ]

    def on_init(self) -> None:
        """策略初始化回调（在添加策略后自动执行）"""
        self.write_log("策略初始化")

        # 创建Bar生成器与ArrayManager
        self.bg: BarGenerator = BarGenerator(self.on_bar)
        self.am: ArrayManager = ArrayManager()

        # 加载一定数量的历史Bar数据，用于初始化技术指标
        self.load_bar(10)

    def on_start(self) -> None:
        """策略启动回调"""
        self.write_log("策略启动")

    def on_stop(self) -> None:
        """策略停止回调"""
        self.write_log("策略停止")

    def on_tick(self, tick: TickData) -> None:
        """收到新的Tick数据推送回调"""
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData) -> None:
        """收到新的Bar数据推送回调"""
        # 1) 更新K线数据
        if not self.update_am(bar):
            return

        # 2) 撤销之前所有未成交委托
        self.cancel_all()

        # 3) 如果是本策略收到的第一根Bar，则先记录后直接返回
        if self.is_first_bar(bar):
            return

        # 4) 检查是否跨日并更新相关变量（day_high、day_low等）
        self.check_new_day(bar)

        # 5) 如果尚未计算出有效的日内区间或技术指标数据尚未初始化完成，则跳过
        if not self.day_range or not self.am.inited:
            return

        # 6) 计算RSI指标
        rsi_value: float = self.calculate_rsi()

        # 7) 执行交易逻辑（开仓/平仓/移动止损等）
        self.execute_trading_logic(bar, rsi_value)

        # 8) 推送策略更新事件
        self.put_event()

    # ------------------------------------------------------------------------
    # 辅助函数
    # ------------------------------------------------------------------------
    def update_am(self, bar: BarData) -> bool:
        """
        更新Bar到ArrayManager，并返回是否初始化完成（即是否已积累足够数据）。
        """
        self.am.update_bar(bar)
        return self.am.inited

    def is_first_bar(self, bar: BarData) -> bool:
        """
        判断是否为第一根Bar。如果是，则仅记录并返回True。
        """
        if not self.last_bar:
            self.last_bar = bar
            return True
        return False

    def check_new_day(self, bar: BarData) -> None:
        """
        判断是否跨交易日；如果跨日则计算前一日range，并重置相关变量。
        否则仅更新最高/最低价。
        """
        # 如果跨日
        if self.last_bar.datetime.date() != bar.datetime.date():
            if self.day_high:  # 原逻辑：只有在非初始情形下才计算日内区间
                self.day_range = self.day_high - self.day_low
                self.long_entry = bar.open_price + self.k1 * self.day_range
                self.short_entry = bar.open_price - self.k2 * self.day_range

            self.day_open = bar.open_price
            self.day_high = bar.high_price
            self.day_low = bar.low_price

            self.long_entered = False
            self.short_entered = False
            self.daily_count = 0
        else:
            # 同一天，持续更新最高/最低价
            self.day_high = max(self.day_high, bar.high_price)
            self.day_low = min(self.day_low, bar.low_price)

        # 更新本Bar作为上一根Bar
        self.last_bar = bar

    def calculate_rsi(self) -> float:
        """计算并返回当前Bar的RSI值。"""
        return self.am.rsi(self.rsi_window)

    def execute_trading_logic(self, bar: BarData, rsi_value: float) -> None:
        """
        核心交易逻辑：
        - 空仓时根据RSI信号判断开仓；
        - 持多/持空时根据移动止损调整持仓并可能反手。
        """
        if self.pos == 0:
            # 记录初始Bar最高/最低，以便后续持仓期间更新
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            # 每日交易次数未达上限 => 允许开仓
            if self.daily_count < self.daily_limit:
                # RSI高于 50 + signal => 开多
                if rsi_value >= 50 + self.rsi_signal:
                    self.buy(self.long_entry, self.fixed_size, stop=True)
                # RSI低于 50 - signal => 开空
                elif rsi_value <= 50 - self.rsi_signal:
                    self.short(self.short_entry, self.fixed_size, stop=True)

        elif self.pos > 0:
            # 更新持仓期间最高/最低价
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            # 计算多头移动止损价
            long_stop: float = self.intra_trade_high * (1 - self.trailing_long / 100)
            # 确保止损价不低于空头开仓位
            long_stop = max(long_stop, self.short_entry)

            # 多头止盈/止损 & 反手空单
            self.sell(long_stop, self.fixed_size, stop=True)
            self.short(self.short_entry, self.fixed_size, stop=True)

        elif self.pos < 0:
            # 更新持仓期间最高/最低价
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)

            # 计算空头移动止损价
            short_stop: float = self.intra_trade_low * (1 + self.trailing_short / 100)
            # 确保止损价不高于多头开仓位
            short_stop = min(short_stop, self.long_entry)

            # 空头止盈/止损 & 反手多单
            self.cover(short_stop, self.fixed_size, stop=True)
            self.buy(self.long_entry, self.fixed_size, stop=True)

    # ------------------------------------------------------------------------
    # 以下回调函数无需更改或仅作空实现
    # ------------------------------------------------------------------------
    def on_order(self, order: OrderData) -> None:
        """新的订单数据更新回调"""
        pass

    def on_trade(self, trade: TradeData) -> None:
        """新的成交数据更新回调"""
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder) -> None:
        """停止单更新回调"""
        pass
