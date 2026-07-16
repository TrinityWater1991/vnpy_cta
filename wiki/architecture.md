---
title: "系统架构"
category: "reference"
tags: [architecture, components, data-flow]
created: 2026-07-16
updated: 2026-07-16
---

# 系统架构

> 本页描述 vnpy_cta 系统的技术架构、组件关系和数据流。

## 架构概览

<!-- TODO: 架构图（ASCII 或图片引用） -->

## 组件清单

### 核心组件

| 组件 | 说明 | 技术选型 |
|------|------|----------|
| CTA 引擎 | 策略调度与信号执行 | vnpy CtaEngine |
| 行情网关 | 实时行情接入 | CTP Gateway |
| 交易网关 | 订单路由与执行 | CTP Gateway |
| 数据库 | 行情与交易数据持久化 | SQLite（本地 .vntrader/） |
| 进程守护 | 保证系统持续运行 | systemd |

### 辅助组件

| 组件 | 说明 | 技术选型 |
|------|------|----------|
| 监控面板 | 可视化监控 | （待确定：Grafana / vnpy 内置） |
| 告警通知 | 异常事件推送 | （待确定：钉钉 / 微信 / 邮件） |
| 日志系统 | 日志采集与查询 | journald / 文件日志 |
| 备份系统 | 数据定时备份 | cron + scripts/backup.sh |

## 数据流

```
行情源 (CTP) → 行情网关 → CTA 引擎 → 策略逻辑 → 信号 → 交易网关 → 交易所
                      ↓
                   数据库 (SQLite)
```

## 网络拓扑

<!-- TODO: VPS 网络配置、端口映射、安全组规则 -->

- VPS IP: 47.237.121.19
- SSH 端口: （待补充）
- CTP 行情/交易端口: （待补充）

## 相关页面

- [[deployment/deploy-workflow]] — 部署流程
- [[deployment/network-security]] — 网络安全配置
- [[monitoring/metrics]] — 监控指标
