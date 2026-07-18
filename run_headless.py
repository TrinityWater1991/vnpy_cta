#!/usr/bin/env python3.13
"""
vnpy CTA 无界面实盘运行脚本。

参考 vnpy 官方 examples/no_ui/run.py 的初始化流程：
  - init_engine() → init_all_strategies() → sleep(60) → start_all_strategies()
  - LogEngine 注册 EVENT_CTA_LOG 事件
  - main_engine.add_gateway() 添加交易所网关

与官方脚本的不同：
  - 策略从 configs/cta_strategy_setting.json 加载（而非硬编码）
  - 网关动态加载（当前为 Bitget，待开发）
  - 单进程模式，由 systemd 管理生命周期（加密货币 7×24 交易，无需交易时段判断）
"""
from __future__ import annotations

import json
import signal
import sys
from pathlib import Path
from time import sleep

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR / "strategies"))

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine, LogEngine
from vnpy.trader.logger import INFO, logger
from vnpy.trader.setting import SETTINGS

# ── vnpy 内置策略注册（CtaEngine 按类名自动发现） ──────────
import vnpy_ctastrategy.strategies.atr_rsi_strategy           # noqa: F401
import vnpy_ctastrategy.strategies.boll_channel_strategy      # noqa: F401
import vnpy_ctastrategy.strategies.double_ma_strategy         # noqa: F401
import vnpy_ctastrategy.strategies.dual_thrust_strategy       # noqa: F401
import vnpy_ctastrategy.strategies.king_keltner_strategy      # noqa: F401
import vnpy_ctastrategy.strategies.multi_signal_strategy      # noqa: F401
import vnpy_ctastrategy.strategies.multi_timeframe_strategy   # noqa: F401
import vnpy_ctastrategy.strategies.turtle_signal_strategy     # noqa: F401

from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctastrategy.base import EVENT_CTA_LOG
from vnpy_ctastrategy.engine import CtaEngine

# ── 自定义策略模块注册（仅导入 cta_strategy_setting.json 中配置的策略） ──
import multi_ma_trend_strategy                    # noqa: F401
import intraday_momentum_strategy                 # noqa: F401
import concretum_dual_channel_v2b_strategy        # noqa: F401
import turtle_trading_strategy                    # noqa: F401

# ── 配置路径 ──────────────────────────────────────────────

SETTINGS["log.active"] = True
SETTINGS["log.level"] = INFO
SETTINGS["log.console"] = True
SETTINGS["log.file"] = True

STRATEGY_CONFIG_PATH = PROJECT_DIR / "configs" / "cta_strategy_setting.json"
GATEWAY_CONFIG_PATH = PROJECT_DIR / "configs" / "vt_setting.json"


def load_gateway() -> object | None:
    """
    动态加载交易所网关模块并返回 Gateway 类。
    目前为 Bitget 占位，待开发完成后取消注释对应行。
    """
    # TODO: Bitget gateway 开发完成后启用以下代码
    # from vnpy_bitget import BitgetGateway
    # return BitgetGateway

    # 国内期货 CTP（已废弃，保留参考）
    # from vnpy_ctp import CtpGateway
    # return CtpGateway

    logger.warning("未配置交易所网关")
    return None


def load_gateway_setting() -> dict:
    """从 vt_setting.json 加载网关连接参数。"""
    if GATEWAY_CONFIG_PATH.exists():
        raw = json.loads(GATEWAY_CONFIG_PATH.read_text(encoding="utf-8"))
        return raw.get("gateway", raw)
    return {}


def load_strategies(cta_engine: CtaEngine) -> int:
    """从配置文件加载策略实例，返回成功加载数量。"""
    if not STRATEGY_CONFIG_PATH.exists():
        logger.warning(f"策略配置文件不存在: {STRATEGY_CONFIG_PATH}")
        return 0

    config = json.loads(STRATEGY_CONFIG_PATH.read_text(encoding="utf-8"))
    count = 0

    for item in config.get("strategies", []):
        try:
            cta_engine.add_strategy(
                item["class_name"],
                item["strategy_name"],
                item["vt_symbol"],
                item.get("setting", {}),
            )
            logger.info(f"策略加载: {item['strategy_name']} ({item['class_name']}) @ {item['vt_symbol']}")
            count += 1
        except Exception as e:
            logger.error(f"策略加载失败: {item.get('strategy_name', '?')} — {e}")

    return count


def main() -> None:
    """主入口：初始化引擎 → 注册网关 → 加载策略 → 持续运行。"""
    logger.info("vnpy CTA 实盘交易系统启动中...")
    logger.info(f"项目目录: {PROJECT_DIR}")

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    # 1. 注册交易所网关
    gateway_class = load_gateway()
    if gateway_class is not None:
        main_engine.add_gateway(gateway_class)

    # 2. 加载 CTA 策略引擎
    cta_engine: CtaEngine = main_engine.add_app(CtaStrategyApp)
    logger.info("主引擎创建成功")

    # 3. 注册 CTA 日志事件 → 日志引擎
    log_engine: LogEngine = main_engine.get_engine("log")       # type: ignore[assignment]
    event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
    logger.info("注册日志事件监听")

    # 4. 连接网关
    if gateway_class is not None:
        gateway_setting = load_gateway_setting()
        gateway_name = getattr(gateway_class, "default_name", gateway_class.__name__.replace("Gateway", ""))
        main_engine.connect(gateway_setting, gateway_name)
        logger.info(f"连接{gateway_name}接口")
        sleep(10)  # 等待连接建立

    # 5. 初始化 CTA 引擎（注册策略类、数据服务、事件监听）
    cta_engine.init_engine()
    logger.info("CTA策略引擎初始化成功")

    # 6. 加载策略配置 + 初始化 + 启动
    # 参考官方 no_ui/run.py: init_all_strategies → sleep(60) → start_all_strategies
    count = load_strategies(cta_engine)
    logger.info(f"策略加载完成，共 {count} 个")

    # 6. 初始化 + 启动所有策略
    # 参考官方 no_ui/run.py: init_all_strategies → sleep(60) → start_all_strategies
    cta_engine.init_all_strategies()
    sleep(60)  # 留足时间让策略完成初始化（load_bar 等）
    logger.info("CTA策略全部初始化")

    cta_engine.start_all_strategies()
    logger.info("CTA策略全部启动，系统运行中...")

    # 7. 持续运行（systemd 管理生命周期）
    while True:
        sleep(10)


if __name__ == "__main__":
    main()
