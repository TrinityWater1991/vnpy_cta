"""双均线期货 CTA 策略回测。

策略逻辑: 快线金叉慢线做多, 死叉做空, 双向可反手, 自首个信号起始终持有一个方向。
成交约定: 信号在 bar 收盘产生, 次根开盘成交, 规避未来函数。
盈亏约定: 跳空(开盘-上收盘)归上一根方向, bar 内(收盘-开盘)归本根方向, 严格对齐持仓。
数据: wiki/raw/jm99_DCE_1m.csv (豆粕主力 jm99, 1 分钟 K 线)。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---- 豆粕 jm 合约与回测参数 ----
DATA_PATH = Path(__file__).resolve().parent.parent / "wiki" / "raw" / "jm99_DCE_1m.csv"
INITIAL_CAPITAL = 100_000.0
MULTIPLIER = 10.0      # 10 吨/手
LOTS = 1.0            # 固定 1 手
FEE_RATE = 1.5e-4      # 手续费率, 双边各收
SLIPPAGE_TICKS = 1.0   # 滑点跳数
TICK_SIZE = 1.0       # 最小变动价位(元/吨)


def load_bars(path: Path) -> pd.DataFrame:
    """读取 1 分钟 K 线, 时间统一到上海时区并排序, 返回 OHLC。"""
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert("Asia/Shanghai")
    df = df.sort_values("datetime")
    df = df.set_index("datetime")
    return df[["open", "high", "low", "close"]].astype(float)


def resample_bars(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """将分钟 OHLC 重采样到更高周期(如 '1h','15min'), 丢弃无交易的空档 bar。"""
    agg = df.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    return agg.dropna()


def compute_target_pos(close: pd.Series, fast: int, slow: int) -> pd.Series:
    """根据快慢均线穿越生成目标方向: 金叉 +1, 死叉 -1, 信号之间前向填充。"""
    fast_ma: pd.Series = close.rolling(fast).mean()
    slow_ma: pd.Series = close.rolling(slow).mean()
    cross_up = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
    cross_dn = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))
    # 用 NaN 初始化: ffill 才能把信号前向延续到下一个反信号, 否则持仓只持 1 根
    target = pd.Series(np.nan, index=close.index)
    target[cross_up.fillna(False)] = 1.0
    target[cross_dn.fillna(False)] = -1.0
    return target.ffill().fillna(0.0)


def run_backtest(df: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    """向量化回测, 返回逐 bar 的持仓、毛盈亏、成本、净盈亏、权益。"""
    open_ = df["open"]
    close = df["close"]

    target = compute_target_pos(close, fast, slow)
    # 次根开盘成交 -> 本根实际持仓方向 = 上根信号方向
    exec_pos = target.shift(1).fillna(0.0)
    prev_pos = exec_pos.shift(1).fillna(0.0)

    overnight = open_ - close.shift(1)   # 跳空: 归上一根方向(持仓过夜到本根开盘)
    intraday = close - open_             # bar 内: 归本根方向(开盘建仓到本根收盘)
    gross_pnl = (prev_pos * overnight + exec_pos * intraday) * MULTIPLIER * LOTS

    delta = (exec_pos - prev_pos).abs()
    trade_lots = delta * LOTS
    tick_value = MULTIPLIER * TICK_SIZE
    cost = (open_ * MULTIPLIER * trade_lots * FEE_RATE
            + SLIPPAGE_TICKS * tick_value * trade_lots)

    net_pnl = gross_pnl - cost
    equity = INITIAL_CAPITAL + net_pnl.cumsum()
    return pd.DataFrame(
        {"close": close, "exec_pos": exec_pos, "gross_pnl": gross_pnl,
         "cost": cost, "net_pnl": net_pnl, "equity": equity},
        index=df.index,
    )


def compute_stats(res: pd.DataFrame) -> dict[str, float]:
    """计算绩效统计: 总收益、年化、最大回撤、夏普、交易次数、胜率、总成本。"""
    equity = res["equity"]
    total_ret = float(equity.iloc[-1] / INITIAL_CAPITAL - 1)
    span_days = max((equity.index[-1] - equity.index[0]).days, 1)
    base = 1.0 + total_ret
    # 权益跌为负(净收益<-100%)时年化无意义, 用 NaN 标记
    ann_ret = float(base ** (365.0 / span_days) - 1.0) if base > 0 else float("nan")

    daily = equity.resample("D").last().dropna()
    daily_ret = daily.pct_change().dropna()
    max_dd = float((daily / daily.cummax() - 1).min())
    sharpe = (float(daily_ret.mean() / daily_ret.std() * np.sqrt(365))
              if daily_ret.std() > 0 else 0.0)

    pos = res["exec_pos"]
    seg = (pos != pos.shift(1)).cumsum()
    seg_net = res["net_pnl"].groupby(seg).sum()
    seg_trades = seg_net.iloc[1:] if len(seg_net) > 1 else seg_net.iloc[0:0]
    n_trades = int(len(seg_trades))
    win_rate = float((seg_trades > 0).mean()) if n_trades > 0 else 0.0

    return {
        "期末权益": float(equity.iloc[-1]),
        "总收益率": total_ret,
        "年化收益率": ann_ret,
        "最大回撤": max_dd,
        "夏普(日,年化365)": sharpe,
        "交易段数": n_trades,
        "胜率": win_rate,
        "总手续费滑点成本": float(res["cost"].sum()),
    }


def plot_equity(equity: pd.Series, out_path: Path) -> Path:
    """绘制日度资金曲线与回撤, 保存为 PNG。"""
    daily = equity.resample("D").last().dropna()
    dd = daily / daily.cummax() - 1.0

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )
    ax1.plot(daily.index, daily.values, lw=1.0, color="#1f77b4")
    ax1.axhline(INITIAL_CAPITAL, color="grey", ls="--", lw=0.8)
    ax1.set_title("Dual MA Strategy - Equity Curve (jm99)")
    ax1.set_ylabel("Equity (CNY)")
    ax1.grid(alpha=0.3)
    ax2.fill_between(dd.index, dd.to_numpy() * 100, 0, color="red", alpha=0.3)
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="双均线期货 CTA 策略回测")
    parser.add_argument("--fast", type=int, default=5, help="快线周期(默认 5)")
    parser.add_argument("--slow", type=int, default=20, help="慢线周期(默认 20)")
    parser.add_argument("--resample", type=str, default=None,
                        help="重采样周期, 如 '1h','15min'; 不填则用原始 1 分钟")
    args = parser.parse_args()
    if args.fast >= args.slow:
        raise SystemExit(f"快线周期须小于慢线周期: fast={args.fast} slow={args.slow}")

    df = load_bars(DATA_PATH)
    if args.resample:
        df = resample_bars(df, args.resample)
    period = args.resample or "1min"
    res = run_backtest(df, args.fast, args.slow)
    stats = compute_stats(res)

    out_path = (Path(__file__).resolve().parent
                / f"equity_curve_dual_ma_{period}_{args.fast}_{args.slow}.png")
    plot_equity(res["equity"], out_path)

    print(f"\n=== 双均线策略回测 (周期={period}, fast={args.fast}, slow={args.slow}) ===")
    print(f"数据范围: {df.index[0]} ~ {df.index[-1]}  共 {len(df)} 根 K 线")
    for k, v in stats.items():
        if k == "交易段数":
            print(f"{k:<16}: {int(v)}")
        elif k == "年化收益率" and pd.isna(v):
            print(f"{k:<16}: N/A (权益为负, 年化无意义)")
        elif k in ("胜率", "总收益率", "年化收益率", "最大回撤"):
            print(f"{k:<16}: {v*100:.2f}%")
        else:
            print(f"{k:<16}: {v:,.2f}")
    print(f"资金曲线已保存: {out_path}\n")


if __name__ == "__main__":
    main()
