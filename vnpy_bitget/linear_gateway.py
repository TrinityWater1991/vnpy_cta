"""
Bitget USDT-margined linear futures gateway for VeighNa — API v3 UTA.

Bitget Unified Trading Account (UTA) 使用 API v3：
- REST: https://api.bitget.com/api/v3/*
- WS Public: wss://ws.bitget.com/v3/ws/public
- WS Private: wss://ws.bitget.com/v3/ws/private

References:
- Bitget API v3 UTA: https://www.bitget.com/api-doc/uta/intro
- vnpy_binance linear_gateway.py (reference implementation)
"""
import base64
import hashlib
import hmac
import json
import time
from copy import copy
from collections.abc import Callable
from datetime import datetime, timedelta
from time import sleep

from numpy import format_float_positional

from vnpy.event import Event, EventEngine
from vnpy.trader.constant import (
    Direction,
    Exchange,
    Product,
    Status,
    OrderType,
    Interval,
)
from vnpy.trader.event import EVENT_TIMER
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    TradeData,
    AccountData,
    ContractData,
    PositionData,
    BarData,
    OrderRequest,
    CancelRequest,
    SubscribeRequest,
    HistoryRequest,
)
from vnpy.trader.utility import ZoneInfo
from vnpy_rest import Request, RestClient, Response
from vnpy_websocket import WebsocketClient


# ── 常量 ─────────────────────────────────────────────────

UTC_TZ = ZoneInfo("UTC")

# REST 地址
REAL_REST_HOST: str = "https://api.bitget.com"

# WebSocket 地址 (v3)
REAL_PUBLIC_HOST: str = "wss://ws.bitget.com/v3/ws/public"
REAL_PRIVATE_HOST: str = "wss://ws.bitget.com/v3/ws/private"

WEBSOCKET_TIMEOUT = 24 * 60 * 60

CATEGORY: str = "USDT-FUTURES"

# 订单状态映射
STATUS_BITGET2VT: dict[str, Status] = {
    "not_activated": Status.NOTTRADED,
    "new": Status.NOTTRADED,
    "partially_filled": Status.PARTTRADED,
    "filled": Status.ALLTRADED,
    "cancelled": Status.CANCELLED,
}

# 订单类型映射
ORDERTYPE_VT2BITGET: dict[OrderType, tuple[str, str]] = {
    OrderType.LIMIT: ("limit", "gtc"),
    OrderType.MARKET: ("market", "gtc"),
    OrderType.FAK: ("limit", "fok"),
    OrderType.FOK: ("limit", "fok"),
}
ORDERTYPE_BITGET2VT: dict[tuple[str, str], OrderType] = {
    v: k for k, v in ORDERTYPE_VT2BITGET.items()
}

# 方向映射
DIRECTION_VT2BITGET: dict[Direction, str] = {
    Direction.LONG: "buy",
    Direction.SHORT: "sell",
}
DIRECTION_BITGET2VT: dict[str, Direction] = {
    v: k for k, v in DIRECTION_VT2BITGET.items()
}

# K 线周期映射
INTERVAL_VT2BITGET: dict[Interval, str] = {
    Interval.MINUTE: "1m",
    Interval.HOUR: "1H",
    Interval.DAILY: "1D",
}

TIMEDELTA_MAP: dict[Interval, timedelta] = {
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta(days=1),
}


# ── BitgetLinearGateway ────────────────────────────────

class BitgetLinearGateway(BaseGateway):
    """Bitget U 本位合约网关 (API v3 UTA)。"""

    default_name: str = "BITGET_LINEAR"

    default_setting: dict = {
        "API Key": "",
        "API Secret": "",
        "API Passphrase": "",
        "Server": ["REAL"],
        "Proxy Host": "127.0.0.1",
        "Proxy Port": 1081,
    }

    exchanges: list[Exchange] = [Exchange.BITGET]

    def __init__(self, event_engine: EventEngine, gateway_name: str) -> None:
        super().__init__(event_engine, gateway_name)
        self.rest_api: RestApi = RestApi(self)
        self.md_api: MdApi = MdApi(self)
        self.trade_api: TradeApi = TradeApi(self)
        self.orders: dict[str, OrderData] = {}
        self.symbol_contract_map: dict[str, ContractData] = {}
        self.name_contract_map: dict[str, ContractData] = {}

    def connect(self, setting: dict) -> None:
        key: str = setting["API Key"]
        secret: str = setting["API Secret"]
        passphrase: str = setting["API Passphrase"]
        server: str = setting["Server"]
        proxy_host: str = setting.get("Proxy Host") or self.default_setting["Proxy Host"]
        proxy_port: int = setting.get("Proxy Port") or self.default_setting["Proxy Port"]

        self.rest_api.connect(key, secret, passphrase, server, proxy_host, proxy_port)
        self.trade_api.connect(key, secret, passphrase, server, proxy_host, proxy_port)
        self.md_api.connect(server, proxy_host, proxy_port)
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)

    def subscribe(self, req: SubscribeRequest) -> None:
        self.md_api.subscribe(req)

    def send_order(self, req: OrderRequest) -> str:
        return self.trade_api.send_order(req)

    def cancel_order(self, req: CancelRequest) -> None:
        self.trade_api.cancel_order(req)

    def query_account(self) -> None:
        pass

    def query_position(self) -> None:
        pass

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        return self.rest_api.query_history(req)

    def close(self) -> None:
        self.rest_api.stop()
        self.md_api.stop()
        self.trade_api.stop()

    def on_order(self, order: OrderData) -> None:
        self.orders[order.orderid] = copy(order)
        super().on_order(order)

    def get_order(self, orderid: str) -> OrderData | None:
        return self.orders.get(orderid, None)

    def on_contract(self, contract: ContractData) -> None:
        self.symbol_contract_map[contract.symbol] = contract
        self.name_contract_map[contract.name] = contract
        super().on_contract(contract)

    def get_contract_by_symbol(self, symbol: str) -> ContractData | None:
        return self.symbol_contract_map.get(symbol, None)

    def get_contract_by_name(self, name: str) -> ContractData | None:
        return self.name_contract_map.get(name, None)

    def process_timer_event(self, event: Event) -> None:
        self.md_api.subscribe_new_channels()


# ── RestApi ─────────────────────────────────────────────

class RestApi(RestClient):
    """Bitget REST API v3 客户端。"""

    def __init__(self, gateway: BitgetLinearGateway) -> None:
        super().__init__()
        self.gateway: BitgetLinearGateway = gateway
        self.gateway_name: str = gateway.gateway_name
        self.key: str = ""
        self.secret: str = ""
        self.passphrase: str = ""
        self.order_prefix: str = ""

    def sign(self, request: Request) -> Request:
        """Bitget API v3 签名。"""
        if request.data and request.data.get("signed", False):
            timestamp: str = str(int(time.time() * 1000))
            method: str = request.method

            request_path: str = request.path
            if request.params:
                query: str = "&".join(
                    f"{k}={v}" for k, v in sorted(request.params.items())
                )
                request_path = request.path + "?" + query

            body: str = ""
            if request.data and request.data.get("body"):
                body = json.dumps(request.data["body"])
                request.data = body

            prehash: str = timestamp + method + request_path + body
            signature: str = base64.b64encode(
                hmac.new(
                    self.secret.encode("utf-8"),
                    prehash.encode("utf-8"),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")

            # 签名完成后清除 data，避免 {"signed": True} 被当作 HTTP body 发送
            request.data = {}

            request.headers = {
                "Content-Type": "application/json",
                "ACCESS-KEY": self.key,
                "ACCESS-SIGN": signature,
                "ACCESS-TIMESTAMP": timestamp,
                "ACCESS-PASSPHRASE": self.passphrase,
                "locale": "en-US",
            }
        else:
            request.headers = {
                "Content-Type": "application/json",
                "locale": "en-US",
            }
        return request

    def connect(
        self, key: str, secret: str, passphrase: str,
        server: str, proxy_host: str, proxy_port: int,
    ) -> None:
        self.key = key
        self.secret = secret
        self.passphrase = passphrase
        self.proxy_port = proxy_port
        self.proxy_host = proxy_host
        self.order_prefix = datetime.now().strftime("%y%m%d%H%M%S")
        self.init(REAL_REST_HOST, proxy_host, proxy_port)
        self.start()
        self.gateway.write_log("REST API started")
        self.query_time()

    # ── v3 public endpoints ──────────────────────────────

    def query_time(self) -> None:
        self.add_request("GET", "/api/v3/market/time", callback=self.on_query_time)

    def query_contract(self) -> None:
        # v2 contracts endpoint still works and returns full contract specs
        self.add_request(
            "GET",
            f"/api/v2/mix/market/contracts?productType={CATEGORY}",
            callback=self.on_query_contract,
        )

    def query_unfilled_orders(self) -> None:
        """v3 UTA unfilled orders (no category param needed)."""
        self.add_request(
            "GET",
            "/api/v3/trade/unfilled-orders",
            callback=self.on_query_order,
            data={"signed": True},
        )

    # ── callbacks ────────────────────────────────────────

    def on_query_time(self, data: dict, request: Request) -> None:
        server_time: int = int(data.get("data", {}).get("serverTime", 0))
        local_time: int = int(time.time() * 1000)
        offset: int = local_time - server_time
        self.gateway.write_log(f"Server time synced, offset: {offset}ms")
        self.query_contract()

    def on_query_contract(self, data: dict, request: Request) -> None:
        items: list = data.get("data", [])
        if not items:
            self.gateway.write_log("No contracts returned")
            return

        for item in items:
            name: str = item.get("symbol", "")
            if not name:
                continue

            symbol: str = name  # vt_symbol 自动拼为 BTCUSDT.BITGET
            pricetick: float = float(item.get("pricePlace", 0) or 0)
            pricetick = 10 ** (-pricetick) if pricetick else 0.01
            volume_place: int = int(item.get("volumePlace", 0) or 0)
            min_volume: float = 10 ** (-volume_place) if volume_place else 0.001

            contract: ContractData = ContractData(
                symbol=symbol,
                exchange=Exchange.BITGET,
                name=name,
                pricetick=pricetick,
                size=1,
                min_volume=min_volume,
                product=Product.SWAP,
                net_position=True,
                history_data=True,
                gateway_name=self.gateway_name,
                stop_supported=False,
            )
            self.gateway.on_contract(contract)

        self.gateway.write_log(f"Contract data received ({len(items)} contracts)")

        # 加载挂单（账户/持仓由 WS 推送）
        if self.key and self.secret:
            self.query_unfilled_orders()
            self.gateway.trade_api.subscribe_user_data_stream()

    def on_query_order(self, data: dict, request: Request) -> None:
        """v3 UTA order list parsing."""
        orders: list = data.get("data", {}).get("list", [])
        for d in orders:
            name: str = d.get("symbol", "")
            contract: ContractData | None = self.gateway.get_contract_by_name(name)
            if not contract:
                continue

            order_type_str: str = d.get("orderType", "limit")
            force: str = d.get("timeInForce", "gtc")
            key: tuple[str, str] = (order_type_str, force)
            order_type: OrderType | None = ORDERTYPE_BITGET2VT.get(key)
            if not order_type:
                order_type = OrderType.LIMIT

            order: OrderData = OrderData(
                orderid=d.get("clientOid", ""),
                symbol=contract.symbol,
                exchange=Exchange.BITGET,
                price=float(d.get("price", 0) or 0),
                volume=float(d.get("qty", 0) or 0),
                type=order_type,
                direction=DIRECTION_BITGET2VT.get(d.get("side", ""), Direction.LONG),
                traded=float(d.get("filledQty", 0) or 0),
                status=STATUS_BITGET2VT.get(d.get("state", ""), Status.NOTTRADED),
                datetime=generate_datetime(int(d.get("cTime", 0))),
                gateway_name=self.gateway_name,
            )
            self.gateway.on_order(order)

        self.gateway.write_log(f"Order data received ({len(orders)} open orders)")

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        contract: ContractData | None = self.gateway.get_contract_by_symbol(req.symbol)
        if not contract:
            return []

        if not req.interval:
            return []

        history: list[BarData] = []
        limit: int = 200
        bitget_interval: str = INTERVAL_VT2BITGET.get(req.interval, "1m")
        end_time: int = int(datetime.timestamp(req.end)) if req.end else int(time.time())
        start_time: int = int(datetime.timestamp(req.start))

        while True:
            params: dict = {
                "symbol": contract.name,
                "granularity": bitget_interval,
                "endTime": str(end_time * 1000),
                "limit": str(limit),
                "productType": CATEGORY,
            }

            resp: Response = self.request(
                "GET", "/api/v2/mix/market/candles", params=params
            )

            if resp.status_code // 100 != 2:
                self.gateway.write_log(
                    f"Query kline failed: {resp.status_code} {resp.text}"
                )
                break

            result: dict = resp.json()
            rows: list = result.get("data", [])
            if not rows:
                break

            buf: list[BarData] = []
            for row in rows:
                bar: BarData = BarData(
                    symbol=req.symbol,
                    exchange=req.exchange,
                    datetime=generate_datetime(int(row[0])),
                    interval=req.interval,
                    volume=float(row[5]),
                    turnover=float(row[6]) if len(row) > 6 else 0,
                    open_price=float(row[1]),
                    high_price=float(row[2]),
                    low_price=float(row[3]),
                    close_price=float(row[4]),
                    gateway_name=self.gateway_name,
                )
                buf.append(bar)

            history.extend(buf)
            self.gateway.write_log(
                f"Kline: {req.symbol} {req.interval.value} "
                f"{buf[0].datetime} — {buf[-1].datetime}"
            )

            if len(rows) < limit:
                break
            if req.end and buf[-1].datetime >= req.end:
                break

            next_end = int(datetime.timestamp(buf[0].datetime)) - 1
            if next_end <= start_time:
                break
            end_time = next_end
            sleep(0.2)

        if history:
            history.pop(-1)
        return history


# ── MdApi ──────────────────────────────────────────────

class MdApi(WebsocketClient):
    """Bitget v3 公共行情 WebSocket。"""

    def __init__(self, gateway: BitgetLinearGateway) -> None:
        super().__init__()
        self.gateway: BitgetLinearGateway = gateway
        self.gateway_name: str = gateway.gateway_name
        self.ticks: dict[str, TickData] = {}
        self.new_channels: list[dict] = []
        self.subscribed: set[str] = set()

    def connect(self, server: str, proxy_host: str, proxy_port: int) -> None:
        self.init(REAL_PUBLIC_HOST, proxy_host, proxy_port, receive_timeout=WEBSOCKET_TIMEOUT)
        self.start()

    def on_connected(self) -> None:
        self.gateway.write_log("MD API connected")
        for symbol in list(self.ticks.keys()):
            contract = self.gateway.get_contract_by_symbol(symbol)
            if not contract:
                continue
            self.send_packet({
                "op": "subscribe",
                "args": [
                    {"instType": CATEGORY, "channel": "ticker", "instId": contract.name},
                    {"instType": CATEGORY, "channel": "books", "instId": contract.name},
                    {"instType": CATEGORY, "channel": "candle1m", "instId": contract.name},
                ],
            })

    def subscribe(self, req: SubscribeRequest) -> None:
        if req.symbol in self.subscribed:
            return
        contract = self.gateway.get_contract_by_symbol(req.symbol)
        if not contract:
            self.gateway.write_log(f"Failed to subscribe, symbol not found: {req.symbol}")
            return

        self.subscribed.add(req.symbol)
        tick: TickData = TickData(
            symbol=req.symbol, name=contract.name, exchange=Exchange.BITGET,
            datetime=datetime.now(UTC_TZ), gateway_name=self.gateway_name,
        )
        tick.extra = {}
        self.ticks[req.symbol] = tick

        self.new_channels.extend([
            {"instType": CATEGORY, "channel": "ticker", "instId": contract.name},
            {"instType": CATEGORY, "channel": "books", "instId": contract.name},
            {"instType": CATEGORY, "channel": "candle1m", "instId": contract.name},
        ])

    def subscribe_new_channels(self) -> None:
        if not self.new_channels:
            return
        self.send_packet({"op": "subscribe", "args": list(self.new_channels)})
        self.new_channels = []

    def on_packet(self, packet: dict) -> None:
        action: str = packet.get("action", "")
        if not action:
            return

        arg: dict = packet.get("arg", {})
        channel: str = arg.get("channel", "")
        inst_id: str = arg.get("instId", "")

        contract = self.gateway.get_contract_by_name(inst_id)
        if not contract:
            return
        tick = self.ticks.get(contract.symbol)
        if not tick:
            return

        data: list = packet.get("data", [])
        if not data:
            return
        item: dict = data[0]

        if channel == "ticker":
            tick.volume = float(item.get("baseVolume", 0) or 0)
            tick.turnover = float(item.get("quoteVolume", 0) or 0)
            tick.open_price = float(item.get("open24h", 0) or 0)
            tick.high_price = float(item.get("high24h", 0) or 0)
            tick.low_price = float(item.get("low24h", 0) or 0)
            tick.last_price = float(item.get("last", 0) or 0)
            tick.datetime = generate_datetime(int(item.get("ts", 0)))
        elif channel == "books":
            asks: list = item.get("asks", [])
            bids: list = item.get("bids", [])
            if bids:
                tick.bid_price_1 = float(bids[0][0])
                tick.bid_volume_1 = float(bids[0][1])
            if asks:
                tick.ask_price_1 = float(asks[0][0])
                tick.ask_volume_1 = float(asks[0][1])
        elif channel == "candle1m":
            candle: list = item if isinstance(item, list) else []
            if len(candle) >= 6:
                if tick.extra is None:
                    tick.extra = {}
                tick.extra["bar"] = BarData(
                    symbol=contract.name, exchange=Exchange.BITGET,
                    datetime=generate_datetime(int(candle[0])), interval=Interval.MINUTE,
                    volume=float(candle[5]), turnover=float(candle[6]) if len(candle) > 6 else 0,
                    open_price=float(candle[1]), high_price=float(candle[2]),
                    low_price=float(candle[3]), close_price=float(candle[4]),
                    gateway_name=self.gateway_name,
                )

        if tick.last_price:
            tick.localtime = datetime.now()
            self.gateway.on_tick(copy(tick))

    def on_disconnected(self, status_code: int, msg: str) -> None:
        self.gateway.write_log(f"MD API disconnected, code: {status_code}, msg: {msg}")

    def on_error(self, e: Exception) -> None:
        self.gateway.write_log(f"MD API exception: {e}")


# ── TradeApi ───────────────────────────────────────────

class TradeApi(WebsocketClient):
    """Bitget v3 私有 WebSocket (下单/撤单/账户/持仓/订单)。"""

    def __init__(self, gateway: BitgetLinearGateway) -> None:
        super().__init__()
        self.gateway: BitgetLinearGateway = gateway
        self.gateway_name: str = gateway.gateway_name
        self.key: str = ""
        self.secret: str = ""
        self.passphrase: str = ""
        self.reqid: int = 0
        self.order_count: int = 0
        self.order_prefix: str = ""
        self.reqid_callback_map: dict[int, Callable] = {}
        self.reqid_order_map: dict[int, OrderData] = {}
        self.logged_in: bool = False
        self.user_stream_subscribed: bool = False

    def connect(
        self, key: str, secret: str, passphrase: str,
        server: str, proxy_host: str, proxy_port: int,
    ) -> None:
        self.key = key
        self.secret = secret
        self.passphrase = passphrase
        self.order_prefix = datetime.now().strftime("%y%m%d%H%M%S")
        self.init(REAL_PRIVATE_HOST, proxy_host, proxy_port, receive_timeout=WEBSOCKET_TIMEOUT)
        self.start()

    def _make_sign(self) -> str:
        ts = str(int(time.time() * 1000))
        return base64.b64encode(
            hmac.new(self.secret.encode(), ts.encode(), hashlib.sha256).digest()
        ).decode(), ts

    def on_connected(self) -> None:
        self.gateway.write_log("Trade API connected")
        sig, ts = self._make_sign()
        self.send_packet({
            "op": "login",
            "args": [{"apiKey": self.key, "passphrase": self.passphrase, "timestamp": ts, "sign": sig}],
        })

    def on_disconnected(self, status_code: int, msg: str) -> None:
        self.logged_in = False
        self.user_stream_subscribed = False
        self.gateway.write_log(f"Trade API disconnected, code: {status_code}, msg: {msg}")

    def on_packet(self, packet: dict) -> None:
        event: str = packet.get("event", "")

        if event == "login":
            code: str = packet.get("code", "")
            if code == "0":
                self.logged_in = True
                self.gateway.write_log("Trade API login success")
                self.subscribe_user_data_stream()
            else:
                self.gateway.write_log(f"Trade API login failed: {packet.get('msg', '')}")
            return

        if event == "subscribe":
            self.gateway.write_log(f"User data stream subscribed: {packet.get('arg', {})}")
            return

        # Push data (event empty or "update"/"snapshot")
        arg: dict = packet.get("arg", {})
        topic: str = arg.get("topic", "")

        if topic == "account":
            self._on_account_update(packet)
        elif topic == "position":
            self._on_position_update(packet)
        elif topic == "order":
            self._on_order_update(packet)

        # API 响应 (place-order / cancel-order)
        if not event and not topic:
            reqid: int = packet.get("requestId", 0)
            callback: Callable | None = self.reqid_callback_map.get(reqid)
            if callback:
                callback(packet)

    def _on_account_update(self, packet: dict) -> None:
        data: list = packet.get("data", [])
        for item in data:
            coin: str = item.get("marginCoin", "USDT")
            available: float = float(item.get("available", 0) or 0)
            frozen: float = float(item.get("frozen", 0) or 0)
            locked: float = float(item.get("locked", 0) or 0)
            balance: float = available + frozen + locked
            if balance:
                self.gateway.on_account(AccountData(
                    accountid=coin, balance=balance, frozen=frozen + locked,
                    gateway_name=self.gateway_name,
                ))

    def _on_position_update(self, packet: dict) -> None:
        data: list = packet.get("data", [])
        for item in data:
            name: str = item.get("symbol", "")
            contract = self.gateway.get_contract_by_name(name)
            if not contract:
                continue
            total: float = float(item.get("size", 0) or 0)
            if total == 0:
                continue
            self.gateway.on_position(PositionData(
                symbol=contract.symbol, exchange=Exchange.BITGET,
                direction=Direction.NET, volume=total,
                price=float(item.get("avgPrice", 0) or 0),
                pnl=float(item.get("unrealizedPnl", 0) or 0),
                gateway_name=self.gateway_name,
            ))

    def _on_order_update(self, packet: dict) -> None:
        data: list = packet.get("data", [])
        for event in data:
            name: str = event.get("symbol", "")
            contract = self.gateway.get_contract_by_name(name)
            if not contract:
                continue

            orderid: str = event.get("clientOid", "")
            order_type_str: str = event.get("orderType", "limit")
            force: str = event.get("timeInForce", "gtc")
            key: tuple[str, str] = (order_type_str, force)
            order_type: OrderType | None = ORDERTYPE_BITGET2VT.get(key)
            if not order_type:
                order_type = OrderType.LIMIT

            order: OrderData = OrderData(
                symbol=contract.symbol, exchange=Exchange.BITGET, orderid=orderid,
                type=order_type,
                direction=DIRECTION_BITGET2VT.get(event.get("side", ""), Direction.LONG),
                price=float(event.get("price", 0) or 0),
                volume=float(event.get("qty", 0) or 0),
                traded=float(event.get("filledQty", 0) or 0),
                status=STATUS_BITGET2VT.get(event.get("state", ""), Status.NOTTRADED),
                datetime=generate_datetime(int(event.get("cTime", 0))),
                gateway_name=self.gateway_name,
            )
            self.gateway.on_order(order)

            # 成交推送
            fill_qty: float = float(event.get("lastFillQty", 0) or 0)
            fill_price: float = float(event.get("lastFillPrice", 0) or 0)
            fill_id: str = event.get("tradeId", "")
            if fill_qty > 0 and fill_price > 0:
                self.gateway.on_trade(TradeData(
                    symbol=contract.symbol, exchange=Exchange.BITGET,
                    orderid=orderid, tradeid=fill_id,
                    direction=DIRECTION_BITGET2VT.get(event.get("side", ""), Direction.LONG),
                    price=fill_price, volume=fill_qty,
                    datetime=generate_datetime(int(event.get("uTime", 0))),
                    gateway_name=self.gateway_name,
                ))

    def send_order(self, req: OrderRequest) -> str:
        contract = self.gateway.get_contract_by_symbol(req.symbol)
        if not contract:
            self.gateway.write_log(f"Failed to send order, symbol not found: {req.symbol}")
            return ""

        self.order_count += 1
        orderid: str = self.order_prefix + str(self.order_count)
        order: OrderData = req.create_order_data(orderid, self.gateway_name)
        self.gateway.on_order(order)

        order_type, force = ORDERTYPE_VT2BITGET[req.type]
        params: dict = {
            "category": CATEGORY,
            "symbol": contract.name,
            "side": DIRECTION_VT2BITGET[req.direction],
            "posSide": DIRECTION_VT2BITGET[req.direction],  # v3 required in hedge mode
            "orderType": order_type,
            "timeInForce": force,
            "qty": format_float(req.volume),
            "clientOid": orderid,
            "price": format_float(req.price) if req.type != OrderType.MARKET else "",
        }

        if req.type == OrderType.MARKET:
            params["orderType"] = "market"
            params["timeInForce"] = "gtc"
            del params["price"]

        self.reqid += 1
        self.reqid_callback_map[self.reqid] = self._on_send_order
        self.reqid_order_map[self.reqid] = order

        sig, ts = self._make_sign()
        self.send_packet({
            "op": "place-order",
            "args": [{**params, "timestamp": ts, "sign": sig}],
            "requestId": str(self.reqid),
        })
        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        contract = self.gateway.get_contract_by_symbol(req.symbol)
        if not contract:
            self.gateway.write_log(f"Failed to cancel order, symbol not found: {req.symbol}")
            return

        self.reqid += 1
        self.reqid_callback_map[self.reqid] = self._on_cancel_order
        sig, ts = self._make_sign()
        self.send_packet({
            "op": "cancel-order",
            "args": [{"symbol": contract.name, "clientOid": req.orderid, "timestamp": ts, "sign": sig}],
            "requestId": str(self.reqid),
        })

    def subscribe_user_data_stream(self) -> None:
        if not self.key or self.user_stream_subscribed:
            return
        self.user_stream_subscribed = True
        self.send_packet({
            "op": "subscribe",
            "args": [
                {"instType": "UTA", "topic": "account"},
                {"instType": "UTA", "topic": "position"},
                {"instType": "UTA", "topic": "order"},
            ],
        })
        self.gateway.write_log("User data stream subscribed")

    def _on_send_order(self, packet: dict) -> None:
        code: str = packet.get("code", "")
        if code == "0":
            return
        self.gateway.write_log(f"Order rejected: {packet.get('msg', '')}")
        request_id: int = int(packet.get("requestId", 0))
        order: OrderData | None = self.reqid_order_map.get(request_id)
        if order:
            order.status = Status.REJECTED
            self.gateway.on_order(order)

    def _on_cancel_order(self, packet: dict) -> None:
        code: str = packet.get("code", "")
        if code == "0":
            return
        self.gateway.write_log(f"Cancel rejected: {packet.get('msg', '')}")

    def on_error(self, e: Exception) -> None:
        self.gateway.write_log(f"Trade API exception: {e}")


# ── 工具函数 ────────────────────────────────────────────

def generate_datetime(timestamp: float) -> datetime:
    if timestamp > 1_000_000_000_000:
        timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp, tz=UTC_TZ)


def format_float(f: float) -> str:
    return format_float_positional(f, trim="-")
