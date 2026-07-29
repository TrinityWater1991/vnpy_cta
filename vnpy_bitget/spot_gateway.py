"""
Bitget spot trading gateway for VeighNa.

References:
- Bitget API v2: https://www.bitget.com/api-doc/common/intro
- vnpy_binance spot_gateway.py (reference implementation)
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

from vnpy.event import EventEngine, Event
from vnpy.trader.event import EVENT_TIMER
from vnpy.trader.constant import (
    Direction,
    Exchange,
    Product,
    Status,
    OrderType,
    Interval,
)
from vnpy.trader.gateway import BaseGateway
from vnpy.trader.object import (
    TickData,
    OrderData,
    TradeData,
    AccountData,
    ContractData,
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
TESTNET_REST_HOST: str = ""

# WebSocket 地址
REAL_DATA_HOST: str = "wss://ws.bitget.com/v2/ws/public"
TESTNET_DATA_HOST: str = ""

REAL_TRADE_HOST: str = "wss://ws.bitget.com/v2/ws/private"
TESTNET_TRADE_HOST: str = ""

# WebSocket 超时
WEBSOCKET_TIMEOUT = 24 * 60 * 60

# 订单状态映射 Bitget → vnpy
STATUS_BITGET2VT: dict[str, Status] = {
    "not_activated": Status.NOTTRADED,
    "new": Status.NOTTRADED,
    "partially_filled": Status.PARTTRADED,
    "filled": Status.ALLTRADED,
    "cancelled": Status.CANCELLED,
}

# 订单类型映射 vnpy → Bitget
ORDERTYPE_VT2BITGET: dict[OrderType, tuple[str, str]] = {
    OrderType.LIMIT: ("limit", "gtc"),
    OrderType.MARKET: ("market", "gtc"),
    OrderType.FAK: ("limit", "fok"),  # Bitget 无 FAK, 用 FOK 近似
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
INTERVAL_BITGET2VT: dict[str, Interval] = {v: k for k, v in INTERVAL_VT2BITGET.items()}

# K 线时间增量
TIMEDELTA_MAP: dict[Interval, timedelta] = {
    Interval.MINUTE: timedelta(minutes=1),
    Interval.HOUR: timedelta(hours=1),
    Interval.DAILY: timedelta(days=1),
}


# ── BitgetSpotGateway ───────────────────────────────────

class BitgetSpotGateway(BaseGateway):
    """
    Bitget 现货交易网关。

    提供 Bitget 现货市场的行情、交易和账户管理功能。
    支持限价单、市价单、FOK 订单类型。
    """

    default_name: str = "BITGET_SPOT"

    default_setting: dict = {
        "API Key": "",
        "API Secret": "",
        "API Passphrase": "",
        "Server": ["REAL"],
        "Proxy Host": "",
        "Proxy Port": 0,
    }

    exchanges: list[Exchange] = [Exchange.GLOBAL]

    def __init__(self, event_engine: EventEngine, gateway_name: str) -> None:
        """初始化网关。"""
        super().__init__(event_engine, gateway_name)

        self.rest_api: RestApi = RestApi(self)
        self.md_api: MdApi = MdApi(self)
        self.trade_api: TradeApi = TradeApi(self)

        self.orders: dict[str, OrderData] = {}
        self.symbol_contract_map: dict[str, ContractData] = {}
        self.name_contract_map: dict[str, ContractData] = {}

    def connect(self, setting: dict) -> None:
        """连接交易所。"""
        key: str = setting["API Key"]
        secret: str = setting["API Secret"]
        passphrase: str = setting["API Passphrase"]
        server: str = setting["Server"]
        proxy_host: str = setting["Proxy Host"]
        proxy_port: int = setting["Proxy Port"]

        self.rest_api.connect(
            key, secret, passphrase, server, proxy_host, proxy_port
        )
        self.trade_api.connect(
            key, secret, passphrase, server, proxy_host, proxy_port
        )
        self.md_api.connect(server, proxy_host, proxy_port)

        self.event_engine.register(EVENT_TIMER, self.process_timer_event)

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情。"""
        self.md_api.subscribe(req)

    def send_order(self, req: OrderRequest) -> str:
        """发送委托。"""
        return self.trade_api.send_order(req)

    def cancel_order(self, req: CancelRequest) -> None:
        """撤销委托。"""
        self.trade_api.cancel_order(req)

    def query_account(self) -> None:
        """查询账户（WebSocket 推送更新，无需主动查询）。"""
        pass

    def query_position(self) -> None:
        """查询持仓（现货无持仓概念）。"""
        pass

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        """查询历史 K 线。"""
        return self.rest_api.query_history(req)

    def close(self) -> None:
        """关闭连接。"""
        self.rest_api.stop()
        self.md_api.stop()
        self.trade_api.stop()

    def on_order(self, order: OrderData) -> None:
        """保存委托副本并推送。"""
        self.orders[order.orderid] = copy(order)
        super().on_order(order)

    def get_order(self, orderid: str) -> OrderData | None:
        """按 orderid 获取委托。"""
        return self.orders.get(orderid, None)

    def on_contract(self, contract: ContractData) -> None:
        """保存合约映射并推送。"""
        self.symbol_contract_map[contract.symbol] = contract
        self.name_contract_map[contract.name] = contract
        super().on_contract(contract)

    def get_contract_by_symbol(self, symbol: str) -> ContractData | None:
        """按 vnpy symbol 获取合约。"""
        return self.symbol_contract_map.get(symbol, None)

    def get_contract_by_name(self, name: str) -> ContractData | None:
        """按交易所原始名称获取合约。"""
        return self.name_contract_map.get(name, None)

    def process_timer_event(self, event: Event) -> None:
        """定时任务：订阅新频道。"""
        self.md_api.subscribe_new_channels()


# ── RestApi ─────────────────────────────────────────────

class RestApi(RestClient):
    """Bitget REST API 客户端。"""

    def __init__(self, gateway: BitgetSpotGateway) -> None:
        """初始化。"""
        super().__init__()

        self.gateway: BitgetSpotGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.key: str = ""
        self.secret: str = ""
        self.passphrase: str = ""

        self.order_count: int = 1_000_000
        self.order_prefix: str = ""
        self.server: str = ""

    def sign(self, request: Request) -> Request:
        """
        Bitget API v2 签名。

        签名算法:
            prehash = timestamp + method + requestPath + body
            signature = Base64(HMAC-SHA256(secret, prehash))

        Headers:
            ACCESS-KEY, ACCESS-SIGN, ACCESS-TIMESTAMP, ACCESS-PASSPHRASE
        """
        if request.data and request.data.get("signed", False):
            timestamp: str = str(int(time.time() * 1000))
            method: str = request.method

            # 构建请求路径（不含 query string）
            request_path: str = request.path
            if request.params:
                query: str = "&".join(
                    f"{k}={v}" for k, v in sorted(request.params.items())
                )
                request_path = request.path + "?" + query

            # 构建签名 body
            body: str = ""
            if request.data and request.data.get("body"):
                body = json.dumps(request.data["body"])
                request.data = body

            # prehash = timestamp + method + requestPath + body
            prehash: str = timestamp + method + request_path + body

            # HMAC-SHA256 → Base64
            signature: str = base64.b64encode(
                hmac.new(
                    self.secret.encode("utf-8"),
                    prehash.encode("utf-8"),
                    hashlib.sha256,
                ).digest()
            ).decode("utf-8")

            # 设置认证 headers
            request.headers = {
                "Content-Type": "application/json",
                "ACCESS-KEY": self.key,
                "ACCESS-SIGN": signature,
                "ACCESS-TIMESTAMP": timestamp,
                "ACCESS-PASSPHRASE": self.passphrase,
                "locale": "en-US",
            }
        else:
            # 公共请求无需签名
            request.headers = {
                "Content-Type": "application/json",
                "locale": "en-US",
            }

        return request

    def connect(
        self,
        key: str,
        secret: str,
        passphrase: str,
        server: str,
        proxy_host: str,
        proxy_port: int,
    ) -> None:
        """建立 REST 连接。"""
        self.key = key
        self.secret = secret
        self.passphrase = passphrase
        self.proxy_port = proxy_port
        self.proxy_host = proxy_host
        self.server = server

        self.order_prefix = datetime.now().strftime("%y%m%d%H%M%S")

        if server == "REAL":
            self.init(REAL_REST_HOST, proxy_host, proxy_port)
        else:
            self.init(TESTNET_REST_HOST, proxy_host, proxy_port)

        self.start()

        self.gateway.write_log("REST API started")

        self.query_time()

    def query_time(self) -> None:
        """查询服务器时间。"""
        self.add_request(
            "GET",
            "/api/v2/public/time",
            callback=self.on_query_time,
        )

    def query_contract(self) -> None:
        """查询交易对信息。"""
        self.add_request(
            "GET",
            "/api/v2/spot/public/symbols",
            callback=self.on_query_contract,
        )

    def query_account(self) -> None:
        """查询账户资产。"""
        self.add_request(
            "GET",
            "/api/v2/spot/account/assets",
            callback=self.on_query_account,
            data={"signed": True},
        )

    def query_order(self) -> None:
        """查询当前挂单。"""
        self.add_request(
            "GET",
            "/api/v2/spot/trade/open-orders",
            callback=self.on_query_order,
            data={"signed": True},
        )

    def on_query_time(self, data: dict, request: Request) -> None:
        """服务器时间回调。"""
        server_time: int = int(data.get("data", {}).get("serverTime", 0))
        local_time: int = int(time.time() * 1000)
        offset: int = local_time - server_time
        self.gateway.write_log(f"Server time synced, offset: {offset}ms")
        self.query_contract()

    def on_query_contract(self, data: dict, request: Request) -> None:
        """解析交易对信息。"""
        symbols: list = data.get("data", [])
        if not symbols:
            self.gateway.write_log("No contracts returned from Bitget")
            return

        for item in symbols:
            name: str = item.get("symbol", "")
            if not name:
                continue

            # Bitget symbol 格式: "BTCUSDT"
            symbol: str = name + "_SPOT_BITGET"

            pricetick: float = float(item.get("priceScale", 0) or 0)
            pricetick = 10 ** (-pricetick) if pricetick else 0.01

            min_volume: float = float(item.get("minTradeAmount", 0.00001) or 0.00001)

            contract: ContractData = ContractData(
                symbol=symbol,
                exchange=Exchange.GLOBAL,
                name=name,
                pricetick=pricetick,
                size=1,
                min_volume=min_volume,
                product=Product.SPOT,
                net_position=True,
                history_data=True,
                gateway_name=self.gateway_name,
                stop_supported=False,
            )
            self.gateway.on_contract(contract)

        self.gateway.write_log(f"Contract data received ({len(symbols)} symbols)")

        # 加载账户和订单
        if self.key and self.secret:
            self.query_order()
            self.query_account()
            self.gateway.trade_api.subscribe_user_data_stream()

    def on_query_account(self, data: dict, request: Request) -> None:
        """解析账户资产。"""
        assets: list = data.get("data", [])
        for item in assets:
            coin: str = item.get("coin", "")
            available: float = float(item.get("available", 0) or 0)
            frozen: float = float(item.get("frozen", 0) or 0)

            if available or frozen:
                account: AccountData = AccountData(
                    accountid=coin,
                    balance=available + frozen,
                    frozen=frozen,
                    gateway_name=self.gateway_name,
                )
                self.gateway.on_account(account)

        self.gateway.write_log("Account data received")

    def on_query_order(self, data: dict, request: Request) -> None:
        """解析当前挂单。"""
        orders: list = data.get("data", [])
        for d in orders:
            order_type_str: str = d.get("orderType", "limit")
            force: str = d.get("force", "gtc")
            key: tuple[str, str] = (order_type_str, force)
            order_type: OrderType | None = ORDERTYPE_BITGET2VT.get(key, None)
            if not order_type:
                continue

            name: str = d.get("symbol", "")
            contract: ContractData | None = self.gateway.get_contract_by_name(name)
            if not contract:
                continue

            order: OrderData = OrderData(
                orderid=d.get("clientOid", ""),
                symbol=contract.symbol,
                exchange=Exchange.GLOBAL,
                price=float(d.get("price", 0) or 0),
                volume=float(d.get("quantity", 0) or 0),
                type=order_type,
                direction=DIRECTION_BITGET2VT.get(d.get("side", ""), Direction.LONG),
                traded=float(d.get("filledQuantity", 0) or 0),
                status=STATUS_BITGET2VT.get(d.get("status", ""), Status.NOTTRADED),
                datetime=generate_datetime(int(d.get("cTime", 0))),
                gateway_name=self.gateway_name,
            )
            self.gateway.on_order(order)

        self.gateway.write_log("Order data received")

    def query_history(self, req: HistoryRequest) -> list[BarData]:
        """查询历史 K 线数据。"""
        contract: ContractData | None = self.gateway.get_contract_by_symbol(req.symbol)
        if not contract:
            return []

        if not req.interval:
            return []

        history: list[BarData] = []
        limit: int = 200

        # Bitget candles API
        bitget_interval: str = INTERVAL_VT2BITGET.get(req.interval, "1m")
        end_time: int = int(datetime.timestamp(req.end)) if req.end else int(time.time())
        start_time: int = int(datetime.timestamp(req.start))

        while True:
            params: dict = {
                "symbol": contract.name,
                "granularity": bitget_interval,
                "endTime": str(end_time * 1000),
                "limit": str(limit),
            }

            resp: Response = self.request(
                "GET",
                "/api/v2/spot/market/candles",
                params=params,
            )

            if resp.status_code // 100 != 2:
                msg: str = (
                    f"Query kline failed, status: {resp.status_code}, "
                    f"msg: {resp.text}"
                )
                self.gateway.write_log(msg)
                break

            result: dict = resp.json()
            rows: list = result.get("data", [])
            if not rows:
                break

            buf: list[BarData] = []
            for row in rows:
                # Bitget candle format: [ts, open, high, low, close, baseVol, quoteVol, ...]
                bar: BarData = BarData(
                    symbol=req.symbol,
                    exchange=req.exchange,
                    datetime=generate_datetime(int(row[0])),
                    interval=req.interval,
                    volume=float(row[5]),
                    turnover=float(row[6]),
                    open_price=float(row[1]),
                    high_price=float(row[2]),
                    low_price=float(row[3]),
                    close_price=float(row[4]),
                    gateway_name=self.gateway_name,
                )
                buf.append(bar)

            history.extend(buf)

            begin: datetime = buf[0].datetime
            end: datetime = buf[-1].datetime
            msg = (
                f"Kline history: {req.symbol} {req.interval.value}, "
                f"{begin} — {end}"
            )
            self.gateway.write_log(msg)

            # Check if we need more data
            if len(rows) < limit:
                break

            if req.end and buf[-1].datetime >= req.end:
                break

            next_end = int(datetime.timestamp(buf[0].datetime)) - 1
            if next_end <= start_time:
                break

            end_time = next_end
            sleep(0.2)

        # Remove last (unclosed) candle
        if history:
            history.pop(-1)

        return history


# ── MdApi ──────────────────────────────────────────────

class MdApi(WebsocketClient):
    """
    Bitget 行情 WebSocket 客户端。

    订阅公共频道：ticker, books, candle1m
    """

    def __init__(self, gateway: BitgetSpotGateway) -> None:
        """初始化。"""
        super().__init__()

        self.gateway: BitgetSpotGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.ticks: dict[str, TickData] = {}
        self.reqid: int = 0
        self.new_channels: list[dict] = []
        self.subscribed: set[str] = set()

    def connect(
        self,
        server: str,
        proxy_host: str,
        proxy_port: int,
    ) -> None:
        """连接行情 WebSocket。"""
        if server == "REAL":
            self.init(
                REAL_DATA_HOST,
                proxy_host,
                proxy_port,
                receive_timeout=WEBSOCKET_TIMEOUT,
            )
        else:
            self.init(
                TESTNET_DATA_HOST,
                proxy_host,
                proxy_port,
                receive_timeout=WEBSOCKET_TIMEOUT,
            )

        self.start()

    def on_connected(self) -> None:
        """连接成功：重新订阅。"""
        self.gateway.write_log("MD API connected")

        for symbol, tick in list(self.ticks.items()):
            contract: ContractData | None = (
                self.gateway.get_contract_by_symbol(symbol)
            )
            if not contract:
                continue

            channels: list[dict] = [
                {"channel": "ticker", "instId": contract.name},
                {"channel": "books", "instId": contract.name},
                {"channel": "candle1m", "instId": contract.name},
            ]

            packet: dict = {
                "op": "subscribe",
                "args": channels,
            }
            self.send_packet(packet)

    def subscribe(self, req: SubscribeRequest) -> None:
        """订阅行情。"""
        if req.symbol in self.subscribed:
            return

        contract: ContractData | None = (
            self.gateway.get_contract_by_symbol(req.symbol)
        )
        if not contract:
            self.gateway.write_log(
                f"Failed to subscribe, symbol not found: {req.symbol}"
            )
            return

        self.subscribed.add(req.symbol)

        tick: TickData = TickData(
            symbol=req.symbol,
            name=contract.name,
            exchange=Exchange.GLOBAL,
            datetime=datetime.now(UTC_TZ),
            gateway_name=self.gateway_name,
        )
        tick.extra = {}
        self.ticks[req.symbol] = tick

        channels: list[dict] = [
            {"channel": "ticker", "instId": contract.name},
            {"channel": "books", "instId": contract.name},
            {"channel": "candle1m", "instId": contract.name},
        ]
        self.new_channels.extend(channels)

    def subscribe_new_channels(self) -> None:
        """定时发送新订阅请求。"""
        if not self.new_channels:
            return

        packet: dict = {
            "op": "subscribe",
            "args": list(self.new_channels),
        }
        self.send_packet(packet)
        self.new_channels = []

    def on_packet(self, packet: dict) -> None:
        """解析行情推送。"""
        # Bitget WS 格式: {"action": "snapshot"/"update", "arg": {...}, "data": [...]}
        action: str = packet.get("action", "")
        if not action:
            return

        arg: dict = packet.get("arg", {})
        if not arg:
            return

        channel: str = arg.get("channel", "")
        inst_id: str = arg.get("instId", "")

        contract: ContractData | None = self.gateway.get_contract_by_name(inst_id)
        if not contract:
            return

        tick: TickData | None = self.ticks.get(contract.symbol)
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
            # Order book: use best bid/ask
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
                    symbol=contract.name,
                    exchange=Exchange.GLOBAL,
                    datetime=generate_datetime(int(candle[0])),
                    interval=Interval.MINUTE,
                    volume=float(candle[5]),
                    turnover=float(candle[6]) if len(candle) > 6 else 0,
                    open_price=float(candle[1]),
                    high_price=float(candle[2]),
                    low_price=float(candle[3]),
                    close_price=float(candle[4]),
                    gateway_name=self.gateway_name,
                )

        if tick.last_price:
            tick.localtime = datetime.now()
            self.gateway.on_tick(copy(tick))

    def on_disconnected(self, status_code: int, msg: str) -> None:
        """断连回调。"""
        self.gateway.write_log(
            f"MD API disconnected, code: {status_code}, msg: {msg}"
        )

    def on_error(self, e: Exception) -> None:
        """异常回调。"""
        self.gateway.write_log(f"MD API exception: {e}")


# ── TradeApi ───────────────────────────────────────────

class TradeApi(WebsocketClient):
    """
    Bitget 交易 WebSocket 客户端。

    私有频道：下单、撤单、用户数据流（订单状态、账户更新）。
    """

    def __init__(self, gateway: BitgetSpotGateway) -> None:
        """初始化。"""
        super().__init__()

        self.gateway: BitgetSpotGateway = gateway
        self.gateway_name: str = gateway.gateway_name

        self.key: str = ""
        self.secret: str = ""
        self.passphrase: str = ""
        self.server: str = ""

        self.reqid: int = 0
        self.order_count: int = 0
        self.order_prefix: str = ""

        self.reqid_callback_map: dict[int, Callable] = {}
        self.reqid_order_map: dict[int, OrderData] = {}

        self.logged_in: bool = False
        self.user_stream_subscribed: bool = False

    def sign(self, params: dict) -> dict:
        """为请求参数添加签名。"""
        timestamp: str = str(int(time.time() * 1000))
        params["timestamp"] = timestamp

        prehash: str = timestamp
        signature: str = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"),
                prehash.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        params["sign"] = signature
        return params

    def connect(
        self,
        key: str,
        secret: str,
        passphrase: str,
        server: str,
        proxy_host: str,
        proxy_port: int,
    ) -> None:
        """连接交易 WebSocket。"""
        self.key = key
        self.secret = secret
        self.passphrase = passphrase
        self.server = server

        self.order_prefix = datetime.now().strftime("%y%m%d%H%M%S")

        if server == "REAL":
            self.init(
                REAL_TRADE_HOST,
                proxy_host,
                proxy_port,
                receive_timeout=WEBSOCKET_TIMEOUT,
            )
        else:
            self.init(
                TESTNET_TRADE_HOST,
                proxy_host,
                proxy_port,
                receive_timeout=WEBSOCKET_TIMEOUT,
            )

        self.start()

    def on_connected(self) -> None:
        """连接成功：登录认证。"""
        self.gateway.write_log("Trade API connected")

        timestamp: str = str(int(time.time() * 1000))
        prehash: str = timestamp
        signature: str = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"),
                prehash.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        login_packet: dict = {
            "op": "login",
            "args": [
                {
                    "apiKey": self.key,
                    "passphrase": self.passphrase,
                    "timestamp": timestamp,
                    "sign": signature,
                }
            ],
        }
        self.send_packet(login_packet)

    def on_disconnected(self, status_code: int, msg: str) -> None:
        """断连回调。"""
        self.gateway.write_log(
            f"Trade API disconnected, code: {status_code}, msg: {msg}"
        )
        self.logged_in = False
        self.user_stream_subscribed = False

    def on_packet(self, packet: dict) -> None:
        """解析交易推送。"""
        # 检查 event 字段
        event: str = packet.get("event", "")

        # 登录成功
        if event == "login":
            code: str = packet.get("code", "")
            if code == "0":
                self.logged_in = True
                self.gateway.write_log("Trade API login success")
                self.subscribe_user_data_stream()
            else:
                msg: str = packet.get("msg", "unknown error")
                self.gateway.write_log(f"Trade API login failed: {msg}")
            return

        # 用户数据流事件
        if event == "subscribe":
            self.gateway.write_log(
                f"User data stream subscribed: {packet.get('arg', {})}"
            )
            return

        # 订单 / 账户更新（event 为空表示数据推送）
        arg: dict = packet.get("arg", {})
        channel: str = arg.get("channel", "")

        if channel == "account":
            self._on_account_update(packet)
        elif channel == "orders":
            self._on_order_update(packet)

        # 交易 API 响应（下单/撤单结果）
        if not event and not channel:
            reqid: int = packet.get("requestId", 0)
            callback: Callable | None = self.reqid_callback_map.get(reqid)
            if callback:
                callback(packet)

    def _on_account_update(self, packet: dict) -> None:
        """处理账户更新。"""
        data: list = packet.get("data", [])
        for item in data:
            coin: str = item.get("coin", "")
            available: float = float(item.get("available", 0) or 0)
            frozen: float = float(item.get("frozen", 0) or 0)

            if available or frozen:
                account: AccountData = AccountData(
                    accountid=coin,
                    balance=available + frozen,
                    frozen=frozen,
                    gateway_name=self.gateway_name,
                )
                self.gateway.on_account(account)

    def _on_order_update(self, packet: dict) -> None:
        """处理订单更新。"""
        data: list = packet.get("data", [])
        for event in data:
            name: str = event.get("symbol", "")
            contract: ContractData | None = self.gateway.get_contract_by_name(name)
            if not contract:
                continue

            orderid: str = event.get("clientOid", "")
            order_type_str: str = event.get("orderType", "limit")
            force: str = event.get("force", "gtc")
            key: tuple[str, str] = (order_type_str, force)
            order_type: OrderType | None = ORDERTYPE_BITGET2VT.get(key)
            if not order_type:
                continue

            order: OrderData = OrderData(
                symbol=contract.symbol,
                exchange=Exchange.GLOBAL,
                orderid=orderid,
                type=order_type,
                direction=DIRECTION_BITGET2VT.get(
                    event.get("side", ""), Direction.LONG
                ),
                price=float(event.get("price", 0) or 0),
                volume=float(event.get("quantity", 0) or 0),
                traded=float(event.get("filledQuantity", 0) or 0),
                status=STATUS_BITGET2VT.get(
                    event.get("status", ""), Status.NOTTRADED
                ),
                datetime=generate_datetime(int(event.get("cTime", 0))),
                gateway_name=self.gateway_name,
            )
            self.gateway.on_order(order)

            # 成交推送
            fill_qty: float = float(event.get("lastFillQuantity", 0) or 0)
            fill_price: float = float(event.get("lastFillPrice", 0) or 0)
            fill_id: str = event.get("tradeId", "")
            if fill_qty > 0 and fill_price > 0:
                trade: TradeData = TradeData(
                    symbol=contract.symbol,
                    exchange=Exchange.GLOBAL,
                    orderid=orderid,
                    tradeid=fill_id,
                    direction=DIRECTION_BITGET2VT.get(
                        event.get("side", ""), Direction.LONG
                    ),
                    price=fill_price,
                    volume=fill_qty,
                    datetime=generate_datetime(int(event.get("uTime", 0))),
                    gateway_name=self.gateway_name,
                )
                self.gateway.on_trade(trade)

    def send_order(self, req: OrderRequest) -> str:
        """发送委托。"""
        contract: ContractData | None = self.gateway.get_contract_by_symbol(req.symbol)
        if not contract:
            self.gateway.write_log(
                f"Failed to send order, symbol not found: {req.symbol}"
            )
            return ""

        self.order_count += 1
        orderid: str = self.order_prefix + str(self.order_count)

        order: OrderData = req.create_order_data(orderid, self.gateway_name)
        self.gateway.on_order(order)

        # 构建请求参数
        params: dict = {
            "symbol": contract.name,
            "side": DIRECTION_VT2BITGET[req.direction],
            "orderType": ORDERTYPE_VT2BITGET[req.type][0],
            "force": ORDERTYPE_VT2BITGET[req.type][1],
            "quantity": format_float(req.volume),
            "clientOid": orderid,
        }

        if req.type == OrderType.MARKET:
            params["orderType"] = "market"
            params["force"] = "gtc"
        else:
            order_type, force = ORDERTYPE_VT2BITGET[req.type]
            params["orderType"] = order_type
            params["force"] = force
            params["price"] = format_float(req.price)

        self.reqid += 1
        self.reqid_callback_map[self.reqid] = self._on_send_order
        self.reqid_order_map[self.reqid] = order

        # 通过 WS 私有频道发送订单（需要先签名）
        timestamp: str = str(int(time.time() * 1000))
        prehash: str = timestamp
        signature: str = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"),
                prehash.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        packet: dict = {
            "op": "place-order",
            "args": [
                {
                    **params,
                    "timestamp": timestamp,
                    "sign": signature,
                }
            ],
            "requestId": str(self.reqid),
        }
        self.send_packet(packet)
        return order.vt_orderid

    def cancel_order(self, req: CancelRequest) -> None:
        """撤销委托。"""
        contract: ContractData | None = self.gateway.get_contract_by_symbol(req.symbol)
        if not contract:
            self.gateway.write_log(
                f"Failed to cancel order, symbol not found: {req.symbol}"
            )
            return

        self.reqid += 1
        self.reqid_callback_map[self.reqid] = self._on_cancel_order

        timestamp: str = str(int(time.time() * 1000))
        prehash: str = timestamp
        signature: str = base64.b64encode(
            hmac.new(
                self.secret.encode("utf-8"),
                prehash.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        packet: dict = {
            "op": "cancel-order",
            "args": [
                {
                    "symbol": contract.name,
                    "clientOid": req.orderid,
                    "timestamp": timestamp,
                    "sign": signature,
                }
            ],
            "requestId": str(self.reqid),
        }
        self.send_packet(packet)

    def subscribe_user_data_stream(self) -> None:
        """订阅用户数据流（账户 + 订单）。"""
        if not self.key or self.user_stream_subscribed:
            return

        self.user_stream_subscribed = True

        # 订阅账户频道
        self.send_packet({
            "op": "subscribe",
            "args": [
                {"channel": "account", "instType": "SPOT"},
                {"channel": "orders", "instType": "SPOT"},
            ],
        })

        self.gateway.write_log("User data stream subscribed")

    def _on_send_order(self, packet: dict) -> None:
        """下单结果回调。"""
        code: str = packet.get("code", "")
        if code == "0":
            return  # success, order update will come via user data stream

        msg: str = packet.get("msg", "unknown error")
        self.gateway.write_log(f"Order rejected: {msg}")

        request_id: int = int(packet.get("requestId", 0))
        order: OrderData | None = self.reqid_order_map.get(request_id)
        if order:
            order.status = Status.REJECTED
            self.gateway.on_order(order)

    def _on_cancel_order(self, packet: dict) -> None:
        """撤单结果回调。"""
        code: str = packet.get("code", "")
        if code == "0":
            return

        msg: str = packet.get("msg", "unknown error")
        self.gateway.write_log(f"Cancel rejected: {msg}")

    def on_error(self, e: Exception) -> None:
        """异常回调。"""
        self.gateway.write_log(f"Trade API exception: {e}")


# ── 工具函数 ────────────────────────────────────────────

def generate_datetime(timestamp: float) -> datetime:
    """将毫秒时间戳转为 UTC datetime。"""
    if timestamp > 1_000_000_000_000:
        timestamp = timestamp / 1000  # 秒级
    return datetime.fromtimestamp(timestamp, tz=UTC_TZ)


def format_float(f: float) -> str:
    """格式化浮点数，避免精度错误。"""
    return format_float_positional(f, trim="-")
