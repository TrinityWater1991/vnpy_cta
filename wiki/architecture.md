---
title: "系统架构"
category: "reference"
tags: [architecture, components, data-flow]
created: 2026-07-16
updated: 2026-07-18
---

# 系统架构

> 参考 vnpy 官方 [examples/no_ui/run.py](https://github.com/vnpy/vnpy/blob/master/examples/no_ui/run.py) 设计。

## 架构概览

```
systemd (vnpy-cta.service)
  └── run_headless.py (Python 3.13)
        ├── EventEngine        — 事件驱动核心
        ├── MainEngine         — 主引擎，管理所有模块
        │     ├── CtaStrategyApp  → CtaEngine  — CTA 策略引擎
        │     ├── Gateway (Bitget)               — 交易所网关（待开发）
        │     └── LogEngine                     — 日志引擎
        ├── 策略模块 (strategies/)               — 自定义策略类
        └── 配置 (configs/)                      — 网关 + 策略参数
```

## 初始化流程（官方 no_ui 模式）

参考 `vnpy/examples/no_ui/run.py` 的启动序列：

```
1. EventEngine() + MainEngine(event_engine)
2. main_engine.add_gateway(GatewayClass)        — 注册交易所网关
3. main_engine.add_app(CtaStrategyApp)          — 加载 CTA 策略引擎
4. event_engine.register(EVENT_CTA_LOG, ...)    — CTA 日志 → 日志引擎
5. main_engine.connect(setting, gateway_name)   — 连接网关
6. sleep(10)                                     — 等待连接建立
7. cta_engine.init_engine()                     — 注册策略类 + 数据服务 + 事件
8. cta_engine.add_strategy(...) × N             — 加载策略实例
9. cta_engine.init_all_strategies()             — 执行各策略 on_init()
10. sleep(60)                                    — 留足 load_bar 时间
11. cta_engine.start_all_strategies()            — 执行各策略 on_start()
12. while True: sleep(10)                        — 持续运行
```

关键细节：
- `init_engine()` 内部调用 `load_strategy_class()` 扫描 `strategies/` 下的所有 `.py` 文件，找到 `CtaTemplate` 子类并注册到 `self.classes` 字典。不调用此方法则 `add_strategy()` 无法找到策略类。
- `init_all_strategies()` 调用每个策略的 `on_init()`，策略内部通过 `self.load_bar(N)` 从数据库加载历史 K 线。需要 `sleep(60)` 留足时间。
- `start_all_strategies()` 调用 `on_start()`，策略开始响应行情推送。
- systemd `ExecStop=/bin/kill -TERM $MAINPID` 触发 `main_engine.close()` → `stop_all_strategies()`，保证 CTP 会话正确释放。

## 组件清单

### 核心组件

| 组件 | 说明 | 技术选型 |
|------|------|----------|
| CTA 引擎 | 策略调度与信号执行 | vnpy CtaEngine |
| 交易所网关 | 行情接入 + 订单路由 | Bitget Gateway（待开发） |
| 数据库 | 行情与交易数据持久化 | SQLite（本地 .vntrader/） |
| 进程守护 | 保证系统持续运行 | systemd |
| 日志引擎 | CTA 日志事件采集 | vnpy LogEngine + EVENT_CTA_LOG |

### 辅助组件

| 组件 | 说明 | 技术选型 |
|------|------|----------|
| 监控面板 | 可视化监控 | （待确定：Grafana） |
| 告警通知 | 异常事件推送 | （待确定：钉钉 / 微信 / 邮件） |
| 备份系统 | 数据定时备份 | cron + scripts/backup.sh |

## 数据流

```
交易所 (Bitget) → Gateway → EventEngine → CtaEngine → Strategy.on_tick()/on_bar()
                                    ↓                        ↓
                              LogEngine                  信号 → buy/sell/short/cover
                                    ↓                        ↓
                              日志文件                   Gateway → 交易所
```

## 进程管理

| 层级 | 工具 | 职责 |
|------|------|------|
| systemd | `vnpy-cta.service` | 开机自启、崩溃重启 (`Restart=on-failure`, `RestartSec=10`) |
| run_headless.py | SIGTERM handler | 优雅退出：`main_engine.close()` → 释放交易所会话 |

## 部署位置

- VPS: `47.237.121.19` (Alibaba Cloud Linux 3)
- 项目路径: `/opt/vnpy_cta`
- Python: 3.13.13 (源码编译)
- 虚拟环境: `/opt/vnpy_cta/.venv`

## 相关页面

- [[deployment/deploy-workflow]] — 部署流程
- [[deployment/process-management]] — systemd 配置
- [[monitoring/metrics]] — 监控指标

