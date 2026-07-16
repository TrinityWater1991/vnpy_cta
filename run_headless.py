#!/usr/bin/env python3.13
"""
vnpy CTA 无界面实盘运行脚本。

替代 run_vnpy.py（GUI 版），适合 VPS 无头环境。
从 configs/cta_strategy_setting.json 加载策略并持续运行。
"""
from __future__ import annotations

import json
import signal
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent

# 将 strategies/ 加入 path，确保策略模块可导入
sys.path.insert(0, str(PROJECT_DIR / "strategies"))

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.setting import SETTINGS
from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctastrategy.strategies import (  # vnpy 内置策略注册
    DoubleMaStrategy,
    AtrRsiStrategy,
    BollChannelStrategy,
    KingKeltnerStrategy,
)

# ── 配置 ────────────────────────────────────────────────

SETTINGS["database.database"] = str(PROJECT_DIR / ".vntrader" / "database.db")
STRATEGY_CONFIG_PATH = PROJECT_DIR / "configs" / "cta_strategy_setting.json"

event_engine: EventEngine | None = None
main_engine: MainEngine | None = None


def load_strategies() -> None:
    """从配置文件加载并启动所有策略。"""
    if not STRATEGY_CONFIG_PATH.exists():
        print(f"[WARN] 策略配置文件不存在: {STRATEGY_CONFIG_PATH}")
        return

    config = json.loads(STRATEGY_CONFIG_PATH.read_text(encoding="utf-8"))
    cta_engine = main_engine.get_engine("CtaStrategy")

    for item in config.get("strategies", []):
        class_name = item["class_name"]
        strategy_name = item["strategy_name"]
        vt_symbol = item["vt_symbol"]
        setting = item.get("setting", {})

        try:
            cta_engine.add_strategy(class_name, strategy_name, vt_symbol, setting)
            print(f"  [OK] 加载策略: {strategy_name} ({class_name}) @ {vt_symbol}")
        except Exception as e:
            print(f"  [FAIL] 加载策略失败: {strategy_name} — {e}")

    cta_engine.init_all_strategies()
    cta_engine.start_all_strategies()
    print(f"策略初始化完成，共 {len(config.get('strategies', []))} 个")


def shutdown(signum=None, frame=None) -> None:
    """优雅退出。"""
    print("\n[INFO] 收到退出信号，正在关闭系统...")
    if main_engine:
        cta_engine = main_engine.get_engine("CtaStrategy")
        if cta_engine:
            cta_engine.stop_all_strategies()
        main_engine.close()
    print("[INFO] 系统已安全退出")
    sys.exit(0)


def main() -> None:
    global event_engine, main_engine

    print("=" * 50)
    print("  vnpy CTA 实盘交易系统启动中...")
    print(f"  项目目录: {PROJECT_DIR}")
    print(f"  配置文件: {STRATEGY_CONFIG_PATH}")
    print("=" * 50)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    # 加载 CTA 策略模块
    main_engine.add_app(CtaStrategyApp)

    # 加载策略
    load_strategies()

    print("[INFO] 系统运行中，按 Ctrl+C 退出...")
    # 保持主线程存活
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
