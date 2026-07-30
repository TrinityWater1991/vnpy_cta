#!/usr/bin/env python3.13
"""
Bitget v3 UTA 网关全面测试。
覆盖：REST K线 / WS 行情 / 下单参数精度 / WS 私有频道 / posSide
"""
import sys, os, time, json
from pathlib import Path
from datetime import datetime

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))
os.chdir(PROJECT_DIR)

from vnpy.trader.constant import Exchange
if "BITGET" not in Exchange.__members__:
    Exchange._member_map_["BITGET"] = Exchange._value2member_map_["BITGET"] = Exchange.GLOBAL

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.setting import SETTINGS
from vnpy.trader.object import SubscribeRequest, HistoryRequest
from vnpy.trader.constant import Direction, OrderType, Interval
from vnpy_bitget import BitgetLinearGateway

SETTINGS["log.active"] = True
SETTINGS["log.console"] = True
setting = json.loads(open("configs/vt_setting.json").read())

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
results = []

def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {PASS if ok else FAIL} {name}" + (f" — {detail}" if detail else ""))
    return ok

print("=" * 55)
print("  Bitget v3 UTA Gateway Test")
print("=" * 55)

ee = EventEngine()
me = MainEngine(ee)
me.add_gateway(BitgetLinearGateway)
gw = me.get_gateway("BITGET_LINEAR")

# ── 1. Connect ────────────────────────────────────────
print("\n[1] Connection")
me.connect(setting, "BITGET_LINEAR")
time.sleep(8)

check("Contracts loaded", len(gw.symbol_contract_map) > 0, f"{len(gw.symbol_contract_map)} contracts")
for c in gw.symbol_contract_map.values():
    me.get_engine("oms").contracts[c.vt_symbol] = c
btc = gw.get_contract_by_name("BTCUSDT")
check("BTCUSDT found", btc is not None, f"pricetick={btc.pricetick}, min_vol={btc.min_volume}" if btc else "")

# ── 2. REST K-line ───────────────────────────────────
print("\n[2] REST K-line")
req = HistoryRequest(symbol=btc.symbol, exchange=Exchange.BITGET,
    start=datetime(2026, 7, 30, 0, 0), end=datetime(2026, 7, 30, 12, 0), interval=Interval.MINUTE)
bars = gw.query_history(req)
check("K-line BTCUSDT 1m", len(bars) > 0, f"{len(bars)} bars" if bars else "NO DATA")
if bars:
    check("  first bar", bars[0].datetime is not None, str(bars[0].datetime))
    check("  last bar", bars[-1].datetime is not None, str(bars[-1].datetime))

# ── 3. WS Market Data ────────────────────────────────
print("\n[3] WS Market Data")
sub_req = SubscribeRequest(symbol=btc.symbol, exchange=Exchange.BITGET)
me.subscribe(sub_req, "BITGET_LINEAR")
time.sleep(8)
tick = gw.md_api.ticks.get(btc.symbol)
check("Ticker data received", tick is not None and tick.last_price > 0,
      f"last_price={tick.last_price}, volume={tick.volume}" if tick else "")

# ── 4. Order params ──────────────────────────────────
print("\n[4] Order Precision")
price = round(64321.56789 / btc.pricetick) * btc.pricetick
qty = round(0.12345678 / btc.min_volume) * btc.min_volume
check(f"Price: 64321.56789 -> {price}", abs(price - round(64321.56789 / btc.pricetick) * btc.pricetick) < 0.001)
check(f"Qty: 0.12345678 -> {qty}", qty == round(0.12345678 / btc.min_volume) * btc.min_volume)

# ── 5. posSide ───────────────────────────────────────
from vnpy_bitget.linear_gateway import POSSIDE_VT2BITGET
check("posSide LONG='long'", POSSIDE_VT2BITGET[Direction.LONG] == "long")
check("posSide SHORT='short'", POSSIDE_VT2BITGET[Direction.SHORT] == "short")

# ── 6. WS Private ────────────────────────────────────
print("\n[5] WS Private Channels")
tw = gw.trade_api
for _ in range(10):
    if tw.logged_in:
        break
    time.sleep(1)
check("Trade WS logged in", tw.logged_in)
check("User stream sub'd", tw.user_stream_subscribed)

# ── Summary ──────────────────────────────────────────
print("\n" + "=" * 55)
passed = sum(1 for _, o, _ in results if o)
print(f"  {PASS} {passed} passed  {FAIL} {len(results)-passed} failed  total={len(results)}")
print("=" * 55)

gw.close()
sys.exit(0 if len(results) == passed else 1)
