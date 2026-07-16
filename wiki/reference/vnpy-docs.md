---
title: vnpy 文档索引
category: reference
tags:
  - vnpy
  - documentation
  - api
created: 2026-07-16
updated: 2026-07-16
---

# vnpy 文档索引

> vn.py 官方文档及常用模块说明汇总。

---

## 官方链接

| 资源 | 地址 |
|------|------|
| 官网 | [https://www.vnpy.com](https://www.vnpy.com) |
| GitHub | [https://github.com/vnpy/vnpy](https://github.com/vnpy/vnpy) |
| 官方文档 | [https://www.vnpy.com/docs](https://www.vnpy.com/docs) |
| 中文社区 | [https://www.vnpy.com/forum](https://www.vnpy.com/forum) |
| 策略示例 | [https://github.com/vnpy/vnpy/tree/master/examples](https://github.com/vnpy/vnpy/tree/master/examples) |

> 更多外部资源参见 [[external-links]]。

---

## 核心模块说明

### CtaEngine

CTA 策略引擎，负责策略的加载、启动、停止及委托管理。

主要职责：

- 策略实例管理（加载/卸载）
- 定时调度（`on_tick` / `on_bar` 推送给策略）
- 委托执行与状态跟踪
- 持仓管理
- 日志记录

### CtaTemplate

所有 CTA 策略的基类。自定义策略需继承此类并实现回调方法。

> 参见 [[commands#Python-vnpy 命令|策略启动命令]] 了解如何加载策略。

### CtpGateway

CTP 柜台接口网关，负责与 CTP 柜台之间的连接与通信。

关键配置项（参见 [[ctp-specs|CTP API 规格]]）：

- `BrokerID`
- `TdAddress`（交易服务器地址）
- `MdAddress`（行情服务器地址）
- `AppID`
- `AuthCode`

---

## 常用 API 参考

### 策略基类方法 (`CtaTemplate`)

| 方法 | 说明 |
|------|------|
| `on_init()` | 策略初始化回调 |
| `on_start()` | 策略启动回调 |
| `on_stop()` | 策略停止回调 |
| `on_tick(tick: TickData)` | Tick 行情推送回调 |
| `on_bar(bar: BarData)` | K 线合成完毕回调 |
| `on_trade(trade: TradeData)` | 成交回报回调 |
| `on_order(order: OrderData)` | 委托状态更新回调 |
| `buy(price, volume)` | 开多 |
| `sell(price, volume)` | 平多 |
| `short(price, volume)` | 开空 |
| `cover(price, volume)` | 平空 |
| `cancel_order(orderid)` | 撤单 |

### CTA 引擎方法 (`CtaEngine`)

| 方法 | 说明 |
|------|------|
| `add_strategy(class_name, vt_symbol, setting)` | 添加策略实例 |
| `init_strategy(strategy_name)` | 初始化策略 |
| `start_strategy(strategy_name)` | 启动策略 |
| `stop_strategy(strategy_name)` | 停止策略 |
| `remove_strategy(strategy_name)` | 移除策略实例 |
| `load_strategy_setting()` | 加载策略配置 |
| `get_strategy_profit()` | 获取策略盈亏 |

### 数据回调参数类型

| 数据结构 | 字段 |
|----------|------|
| `TickData` | `symbol`, `exchange`, `datetime`, `last_price`, `volume`, `bid_price_1~5`, `ask_price_1~5`, `bid_volume_1~5`, `ask_volume_1~5` |
| `BarData` | `symbol`, `exchange`, `datetime`, `open`, `high`, `low`, `close`, `volume`, `turnover` |
| `OrderData` | `symbol`, `orderid`, `direction`, `offset`, `price`, `volume`, `traded`, `status`, `datetime` |
| `TradeData` | `symbol`, `orderid`, `tradeid`, `direction`, `offset`, `price`, `volume`, `datetime` |
| `PositionData` | `symbol`, `direction`, `position`, `yd_position`, `td_position`, `frozen` |

---

## 策略文件结构

```
vnpy_cta/
├── strategies/          # 策略代码
│   └── my_strategy.py
├── cta_setting.json     # 策略配置 (JSON)
├── cta_strategy_data/   # 策略数据文件 (pickle/JSON)
└── wiki/                # 运维知识库 ([[template|事故模板]]等)
```

> 参见 [[commands#文件操作|文件操作命令]] 了解相关维护命令。

---

## TODO

- [ ] 补充各模块配置说明
- [ ] 补充 CtaEngine 事件类型列表
- [ ] 补充回测引擎 API 说明
- [ ] 补充 `vnpy_cta` 项目自有扩展 API
