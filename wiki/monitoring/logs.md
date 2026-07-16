---
title: 日志管理
category: monitoring
tags:
  - 日志
  - logrotate
  - 日志查询
  - 日志告警
  - ELK
created: 2026-07-16
updated: 2026-07-16
---

# 日志管理

本文档定义 vnpy CTA 生产环境的日志分类标准、采集方案、查询示例、日志轮转配置以及基于日志的告警策略。

## 日志类型与来源

### 日志分类表

| 日志类别 | 来源模块 | 输出方式 | 日志级别 | 重要性 |
|---------|---------|---------|---------|-------|
| CTA 引擎日志 | `vnpy.app.cta_strategy` | 文件 | INFO / WARNING / ERROR | 高 |
| 策略日志 | 每个策略实例 | 文件 | DEBUG / INFO / WARNING / ERROR | 高 |
| 交易网关日志 | `vnpy.trader.gateway` | 文件 + 控制台 | INFO / ERROR | 高 |
| 行情网关日志 | `vnpy.trader.gateway` | 文件 + 控制台 | INFO / WARNING / ERROR | 高 |
| CTA 引擎事件日志 | `vnpy.event` | 文件 | DEBUG / INFO | 中 |
| 数据库日志 | `vnpy.database` | 文件 | INFO / WARNING / ERROR | 中 |
| 系统运行日志 | `vnpy.main` | 控制台 | INFO | 低 |
| 风控日志 | `vnpy.app.risk_manager` | 文件 | INFO / WARNING / ERROR | 高 |

### 日志文件路径规范

```
/logs/vnpy/
├── cta_engine/           # CTA 引擎日志
│   ├── cta_engine.log        # 当前日志
│   └── cta_engine.log.1      # 轮转后的历史日志
├── strategies/           # 策略日志（每个策略独立文件）
│   ├── strategy_grid_001.log
│   ├── strategy_grid_002.log
│   └── strategy_turtle_001.log
├── gateway/              # 网关日志
│   ├── gateway_ctp.log
│   ├── gateway_xtp.log
│   └── gateway_marketdata.log
├── events/               # 事件日志
│   └── event_bus.log
├── db/                   # 数据库访问日志
│   └── database.log
└── combined/             # 合并日志（用于集中采集）
    └── vnpy_all.log
```

> TODO: 补充容器化部署下日志的 stdout/stderr 收集配置。
> TODO: 补充日志中敏感信息（账户、密钥）的脱敏规则。

## 日志采集架构

### 方案对比

| 方案 | 采集端 | 传输 | 存储 | 检索 | 适用场景 |
|------|-------|------|------|------|---------|
| ELK (Elasticsearch + Logstash + Kibana) | Filebeat | Logstash | Elasticsearch | Kibana | 完整日志分析平台 |
| Loki + Grafana | Promtail | 直接推送 | Loki | Grafana Explore | 轻量方案，与 [[dashboards]] 集成 |
| 简易文件搜索 | `grep` / `journalctl` | 无 | 本地文件 | `grep` / `awk` | 临时排查 |

> TODO: 补充实际部署选型建议和性能基准测试结果。
> TODO: 补充日志采集的带宽预算和限流配置。

### 推荐方案：Grafana Loki + Promtail

```
┌─────────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  策略服务器   │────▶│ Promtail │────▶│   Loki   │────▶│  Grafana  │
│  /logs/vnpy  │     │  (agent) │     │ (存储)   │     │ (检索)   │
└─────────────┘     └──────────┘     └──────────┘     └──────────┘
```

## 日志查询示例

### Grafana Loki (LogQL) 查询

| 场景 | LogQL 查询 |
|------|-----------|
| 查看所有 ERROR 日志 | `{filename="/logs/vnpy/combined/vnpy_all.log"} \|= "ERROR"` |
| 查看 CTA 引擎错误 | `{filename="/logs/vnpy/cta_engine/cta_engine.log"} \|= "ERROR"` |
| 查看特定策略日志 | `{filename="/logs/vnpy/strategies/strategy_grid_001.log"}` |
| 查看网关连接事件 | `{filename="/logs/vnpy/gateway/gateway_ctp.log"} \|= "connected\|disconnected"` |
| 按时间范围统计错误数 | `count_over_time({filename=~"/logs/vnpy/.*"} \|= "ERROR" [5m])` |
| 查询撤单相关日志 | `{filename=~"/logs/vnpy/strategies/.*"} \|= "撤单\|cancel"` |

### 命令行 grep 查询

```bash
# 查看当前 CTA 引擎错误
grep "ERROR" /logs/vnpy/cta_engine/cta_engine.log

# 查看策略盈亏记录
grep "PnL\|盈亏" /logs/vnpy/strategies/strategy_grid_001.log

# 查看网关重连日志
grep -E "重连|reconnect|disconnect" /logs/vnpy/gateway/gateway_ctp.log

# 统计各策略 ERROR 数量
for f in /logs/vnpy/strategies/*.log; do echo "$(basename $f): $(grep -c 'ERROR' $f)"; done

# 实时跟踪 CTA 引擎日志
tail -f /logs/vnpy/cta_engine/cta_engine.log | grep --line-buffered "ERROR\|WARNING"
```

> TODO: 补充常用排查场景的查询语句速查表（如 "策略未发单"、"频繁撤单"、"成交延迟"等）。

## 日志轮转配置

### logrotate 配置

文件路径：`/etc/logrotate.d/vnpy_cta`

```bash
/logs/vnpy/cta_engine/*.log
/logs/vnpy/strategies/*.log
/logs/vnpy/gateway/*.log
/logs/vnpy/events/*.log
/logs/vnpy/db/*.log
/logs/vnpy/combined/*.log
{
    daily                    # 每日轮转
    rotate 30                # 保留 30 个归档
    maxsize 500M             # 当日志超过 500M 时提前轮转
    missingok                # 日志缺失不报错
    notifempty               # 空文件不轮转
    compress                 # 启用 gzip 压缩
    delaycompress            # 延迟压缩（保留一份未压缩）
    dateext                  # 使用日期后缀
    dateformat -%Y%m%d
    extension .log
    olddir /logs/vnpy/archive  # 归档目录
    create 0644 admin admin    # 新日志文件权限
    postrotate
        # 通知 vnpy 进程重新打开日志文件
        kill -USR1 $(pidof vnpy) || true
    endscript
}
```

### 磁盘预留估算

| 项目 | 日均产生量 | 保留天数 | 总占用 |
|------|----------|---------|-------|
| CTA 引擎日志 | ~50MB | 30 | 1.5GB |
| 策略日志 (10个策略) | ~200MB | 30 | 6GB |
| 网关日志 | ~100MB | 30 | 3GB |
| 其他日志 | ~50MB | 30 | 1.5GB |
| **合计** | **~400MB** | **30** | **~12GB** |

> **建议**: 系统日志分区至少预留 50GB 空间，确保日志归档不会撑爆磁盘。
> TODO: 补充日志压缩比参考（gzip 通常可将文本日志压缩至原大小的 10%-20%）。
> TODO: 补充日志轮转的健康检查脚本（检查最近一次轮转是否成功）。

## 日志告警

基于日志内容的告警作为指标告警的补充，用于捕获无法通过数值指标发现的问题。

### 日志告警规则

| 告警规则 | 查询条件 | 频率 | 等级 | 通知方式 |
|---------|---------|------|------|---------|
| 引擎崩溃 | `ERROR.*异常退出\|Engine crashed\|Segmentation fault` | 实时 | P0 | 即时消息 + 电话 |
| 订单拒单 | `ERROR.*拒绝\|REJECTED\|rejected\|拒绝原因` | 实时 | P0 | 即时消息 + 电话 |
| 网关频繁重连 | WARNING 级别重连 > 3 次 / 5min | 1min 聚合 | P1 | 即时消息 |
| 策略异常退出 | `ERROR.*Strategy.*stop\|异常停止` | 实时 | P1 | 即时消息 |
| 数据写入失败 | `ERROR.*database\|写入失败\|write failed` | 实时 | P1 | 即时消息 |
| 频繁报错 | ERROR 日志 > 10 次 / 5min | 5min 聚合 | P2 | 即时消息 |
| 连接超时 | `WARNING.*timeout\|超时\|TimeOut` | 实时 | P2 | 即时消息 |

### Promtail 告警集成

通过 Promtail 的 pipeline 阶段提取日志指标，写入 Prometheus，再通过 [[alerting]] 的告警规则触发通知：

```yaml
# promtail.yml 配置片段
scrape_configs:
  - job_name: vnpy_cta_errors
    static_configs:
      - targets: [localhost]
        labels:
          job: vnpy_cta
          __path__: /logs/vnpy/**/*.log
    pipeline_stages:
      - match:
          selector: '{job="vnpy_cta"} |= "ERROR"'
          stages:
            - metrics:
                vnpy_log_errors_total:
                  type: Counter
                  description: "Total vnpy ERROR log lines"
                  config:
                    match_all: true
                    action: inc
      - match:
          selector: '{job="vnpy_cta"} |= "REJECTED"'
          stages:
            - metrics:
                vnpy_order_rejected_total:
                  type: Counter
                  description: "Orders rejected by exchange"
                  config:
                    match_all: true
                    action: inc
```

> TODO: 补充日志告警的去重规则，避免反复告警造成通知风暴。
> TODO: 补充日志采样率的配置（DEBUG 日志采集频率限制）。
> TODO: 补充日志监控的 dashboard 配置，参见 [[dashboards]]。

## 日志审计与合规

| 要求 | 说明 | 实现方式 |
|------|------|---------|
| 操作审计 | 记录用户操作和系统变更 | 操作日志单独输出到 audit 文件 |
| 日志不可篡改 | 确保日志产生后不被修改 | 仅追加模式、日志签名 |
| 合规保留 | 满足监管机构保留期限要求 | 归档日志备份到对象存储（保存 ≥ 5 年） |

> TODO: 补充日志审计合规检查清单。

## 相关文档

- [[metrics]] — 核心监控指标定义
- [[alerting]] — 告警规则与通知配置
- [[dashboards]] — 监控面板配置（Grafana）
