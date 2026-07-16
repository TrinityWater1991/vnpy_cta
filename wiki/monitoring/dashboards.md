---
title: 监控面板配置
category: monitoring
tags:
  - 监控面板
  - Grafana
  - 可视化
  - 仪表盘
created: 2026-07-16
updated: 2026-07-16
---

# 监控面板配置

本文档定义 vnpy CTA 生产环境的 Grafana 监控面板布局和配置。面板分为四大板块：系统总览、交易监控、风险监控和策略监控。

## Grafana 基础配置

| 配置项 | 推荐值 | 说明 |
|-------|-------|------|
| 数据源 | Prometheus + InfluxDB | 系统指标用 Prometheus，交易/风险/策略指标用 InfluxDB |
| 刷新间隔 | 10s | 与指标采集频率保持一致 |
| 时区 | Asia/Shanghai | CTA 交易时段以北京时间为准 |
| 告警集成 | 内置 Alerting | 对接 Alertmanager 或 Grafana Alerting NG |

> TODO: 补充 Grafana 版本要求和升级策略。
> TODO: 补充面板 JSON 模型的版本管理方式（git 存储 / Grafana API 导出）。

## 面板一：系统总览

**用途**：快速定位基础设施问题。

### 行 1 — 关键状态卡片

| 卡片 | 数据源 | 查询方式 | 展示类型 |
|------|-------|---------|---------|
| 主机在线状态 | Prometheus | `up{job="node_exporter"}` | Stat |
| CPU 使用率 | Prometheus | `100 - avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100` | Stat |
| 内存使用率 | Prometheus | `(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100` | Stat |
| 磁盘使用率 | Prometheus | `(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100` | Stat |
| 网络延迟 (ping) | Prometheus | `probe_duration_seconds` | Stat |

### 行 2 — 系统资源时序图

| 面板 | 数据源 | 图表类型 | 时间范围 |
|------|-------|---------|---------|
| CPU 各核心使用率 | Prometheus | Time Series | 1h / 6h / 1d |
| 内存使用详情 (total/used/cached/buffers) | Prometheus | Time Series | 1h / 6h / 1d |
| 磁盘 IO (read/write bytes) | Prometheus | Time Series | 1h / 6h / 1d |
| 网络带宽 (in/out) | Prometheus | Time Series | 1h / 6h / 1d |

### 行 3 — 进程状态

| 面板 | 查询 | 展示 |
|------|------|------|
| vnpy 进程存活 | `process_up{process="vnpy"}` | Stat / 列表 |
| CTA 引擎运行时长 | `process_uptime{process="vnpy_cta_engine"}` | Stat |

> TODO: 补充 GPU / 加速卡监控面板（如适用）。
> TODO: 补充硬件温度、风扇转速等硬件健康面板。

## 面板二：交易监控

**用途**：监控交易链路质量和网关状态。

### 行 1 — 行情延迟

| 面板 | 查询 | 图表类型 | 告警联动 |
|------|------|---------|---------|
| tick 到达延迟 (ms) | `marketdata_tick_latency_ms` | Time Series | 关联 [[alerting]] P1 规则 |
| K线合成延迟 (ms) | `marketdata_bar_latency_ms` | Time Series | 关联 P1 规则 |
| 行情网关连接数 | `marketdata_gateway_connected` | Stat | 关联 P0 规则 |

### 行 2 — 订单执行

| 面板 | 查询 | 图表类型 | 说明 |
|------|------|---------|------|
| 订单 RTT 分布 (p50/p95/p99) | `order_rtt_ms` | Time Series | 各百分位延迟 |
| 撤单率 (1min 窗口) | `order_cancel_rate` | Time Series | 关联 [[alerting]] P1 规则 |
| 成交率 (1min 窗口) | `order_fill_rate` | Time Series | 监控成交质量 |
| 订单拒绝计数 | `order_rejected_total` | Bar Gauge | 拒绝数累计 |
| 活跃订单数 | `order_pending_total` | Stat | 当前待处理订单 |

### 行 3 — 交易活跃度

| 面板 | 查询 | 图表类型 |
|------|------|---------|
| 每分钟交易量 | `sum(rate(order_submitted_total[1m]))` | Time Series |
| 累计今日交易数 | `increase(order_submitted_total[24h])` | Stat |

> TODO: 补充交易所网关各自的延迟对比面板（CTP vs XTP vs 其他）。
> TODO: 补充不同合约的交易量排行面板。

## 面板三：风险监控

**用途**：实时监控资金风险和持仓风险。

| 面板 | 查询 | 图表类型 | 说明 |
|------|------|---------|------|
| 当前回撤 | `risk_drawdown_current` | Time Series + Stat | 标红超过阈值 |
| 累计 PnL | `risk_pnl_daily` | Bar Gauge / Time Series | 日内逐笔累加 |
| 资金使用率 | `risk_capital_usage_ratio` | Gauge | 以颜色区分安全区 |
| 持仓集中度 | `risk_position_concentration` | Bar Gauge | 按品种聚合 |
| 杠杆倍数 | `risk_leverage` | Stat | 实时显示 |
| 持仓品种分布 | `risk_position_value{contract=~".*"}` | Pie Chart / Bar | 按品种展示占比 |
| 风险评分 | 综合多项指标计算 | Stat / Heatmap | 0-100 分 |

> TODO: 补充压力测试情景下的风险面板切换方案（一键切换到压力测试视图）。
> TODO: 补充保证金快照和历史曲线面板。
> TODO: 补充交易所端的资金流水核对面板。

风险面板的阈值设定和告警规则详情请参见 [[alerting]]。

## 面板四：策略监控

**用途**：按策略实例展示交易表现和信号状态。

### 策略概览表格

使用 Table 面板展示所有策略实例的核心 KPI：

| 列 | 数据源 | 格式 |
|----|-------|------|
| 策略名称 | `strategy_name` | 文本 |
| 状态 | `strategy_status` | 图标 (running/stopped/error) |
| 持仓方向 | `strategy_position_direction` | 文本 (多/空/空仓) |
| 当日 PnL | `strategy_pnl_daily` | 数值 (绿色/红色) |
| 累计 PnL | `strategy_pnl_total` | 数值 |
| 当前回撤 | `strategy_drawdown_current` | 百分比 |
| 交易次数 | `strategy_trade_count` | 数值 |
| 胜率 | `strategy_win_rate` | 百分比 |
| 夏普比 | `strategy_sharpe_ratio` | 数值 |
| 最后信号时间 | `strategy_last_signal_time` | 时间戳 |

### 策略信号时序图

每个策略独立面板，展示：

- **信号点**: 用 marker 在时序图上标出信号发出位置（买入/卖出/平仓）
- **持仓变化**: 阶梯图展示持仓量变化
- **权益曲线**: 策略累计净值曲线

> TODO: 补充策略信号与行情的叠加对比面板（验证信号是否在合理价格发出）。
> TODO: 补充策略参数热力图面板（用于参数敏感性分析）。

## 面板布局推荐

### 大屏监控（推荐 1920x1080）

```
+------------------+------------------+------------------+
|   系统总览 (4行)  |   交易监控 (3行)  |   风险监控 (2行)  |
+------------------+------------------+------------------+
|                  策略监控 (3行)                         |
+------------------------------------------------------+
```

### 移动端适配

| 视图 | 布局 | 自动刷新 |
|------|------|---------|
| 首页 | 仅显示 Stat 卡片和关键告警 | 30s |
| 详细 | 按板块折叠展开 | 手动刷新 |

> TODO: 完善 Grafana 面板的 JSON 模型导出文件，统一存储在 `wiki/grafana/` 目录下。
> TODO: 补充面板的权限管理配置（只读用户 vs 编辑用户）。

## 相关文档

- [[metrics]] — 核心监控指标定义
- [[alerting]] — 告警规则与通知配置
- [[logs]] — 日志管理与分析
