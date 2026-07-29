"""
vnpy CTA 无界面实盘运行脚本。

基于 vnpy 官方 examples/no_ui/run.py，适配 Bitget U 本位合约 7×24 交易。
与官方的差异：
  - 网关: BitgetLinearGateway 替代 CtpGateway
  - 策略: 从 configs/cta_strategy_setting.json 加载（官方从 vt_setting.json 保存的配置加载）
  - 进程: 单进程 + systemd 管理（加密货币全天交易，无需交易时段判断）
"""
import json
import signal
import sys
from pathlib import Path
from time import sleep

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "strategies"))

from vnpy.event import EventEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.engine import MainEngine, LogEngine
from vnpy.trader.logger import INFO, logger

# 官方内置策略注册
import vnpy_ctastrategy.strategies.atr_rsi_strategy           # noqa
import vnpy_ctastrategy.strategies.boll_channel_strategy      # noqa
import vnpy_ctastrategy.strategies.double_ma_strategy         # noqa
import vnpy_ctastrategy.strategies.dual_thrust_strategy       # noqa
import vnpy_ctastrategy.strategies.king_keltner_strategy      # noqa
import vnpy_ctastrategy.strategies.multi_signal_strategy      # noqa
import vnpy_ctastrategy.strategies.multi_timeframe_strategy   # noqa
import vnpy_ctastrategy.strategies.turtle_signal_strategy     # noqa

# 自定义策略 + 网关
import multi_ma_trend_strategy                                # noqa
import intraday_momentum_strategy                             # noqa
import concretum_dual_channel_v2b_strategy                    # noqa
import turtle_trading_strategy                                # noqa

from vnpy_ctastrategy import CtaStrategyApp, CtaEngine
from vnpy_ctastrategy.base import EVENT_CTA_LOG
from vnpy_bitget import BitgetLinearGateway


SETTINGS["log.active"] = True
SETTINGS["log.level"] = INFO
SETTINGS["log.console"] = True
SETTINGS["log.file"] = True

# ── 配置加载 ──────────────────────────────────────────────

GATEWAY_CONFIG_PATH = PROJECT_DIR / "configs" / "vt_setting.json"
STRATEGY_CONFIG_PATH = PROJECT_DIR / "configs" / "cta_strategy_setting.json"


def load_gateway_setting() -> dict:
    """加载网关连接参数。"""
    if GATEWAY_CONFIG_PATH.exists():
        return json.loads(GATEWAY_CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def load_custom_strategies(cta_engine: CtaEngine) -> int:
    """从 JSON 配置文件加载策略实例（本项目的扩展功能）。"""
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


# ── 主入口 ────────────────────────────────────────────────

def main() -> None:
    """主入口（官方 no_ui/run.py 启动序列）。"""
    logger.info("vnpy CTA 实盘交易系统启动中...")

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(BitgetLinearGateway)
    cta_engine: CtaEngine = main_engine.add_app(CtaStrategyApp)
    logger.info("主引擎创建成功")

    log_engine: LogEngine = main_engine.get_engine("log")       # type: ignore
    event_engine.register(EVENT_CTA_LOG, log_engine.process_log_event)
    logger.info("注册日志事件监听")

    # 连接网关
    gateway_setting = load_gateway_setting()
    main_engine.connect(gateway_setting, "BITGET_LINEAR")
    logger.info("连接BITGET_LINEAR接口")
    sleep(10)

    # 初始化 CTA 引擎
    cta_engine.init_engine()
    logger.info("CTA策略初始化完成")

    # 加载自定义策略（官方无此步骤，策略通过 init_engine 从 vt_setting 加载）
    load_custom_strategies(cta_engine)

    cta_engine.init_all_strategies()
    sleep(60)
    logger.info("CTA策略全部初始化")

    cta_engine.start_all_strategies()
    logger.info("CTA策略全部启动")

    # 持续运行（加密货币 7×24 交易，不需要交易时段判断）
    while True:
        sleep(10)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    main()
