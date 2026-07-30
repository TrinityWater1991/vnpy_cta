"""
vnpy GUI 调试启动脚本。

基于官方 examples/veighna_trader/run.py，加载 CTA 策略引擎 + 数据管理 + Bitget U 本位合约网关。
用于本地开发调试：查看行情、管理数据、手动加载策略。
"""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "strategies"))

# 注册 BITGET 交易所枚举
from vnpy.trader.constant import Exchange
if "BITGET" not in Exchange.__members__:
    Exchange._member_map_["BITGET"] = Exchange._value2member_map_["BITGET"] = Exchange.GLOBAL
    Exchange._member_names_.append("BITGET")  # type: ignore[attr-defined]

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import MainWindow, create_qapp

from vnpy_bitget import BitgetLinearGateway
from vnpy_ctastrategy import CtaStrategyApp
from vnpy_ctabacktester import CtaBacktesterApp
from vnpy_datamanager import DataManagerApp


def main():
    qapp = create_qapp()

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)

    main_engine.add_gateway(BitgetLinearGateway)
    main_engine.add_app(CtaStrategyApp)
    main_engine.add_app(CtaBacktesterApp)
    main_engine.add_app(DataManagerApp)

    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()

    qapp.exec()


if __name__ == "__main__":
    main()
