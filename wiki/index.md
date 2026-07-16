---
title: "WIKI 索引"
category: "reference"
tags: [index]
created: 2026-07-16
updated: 2026-07-16
---

# WIKI 索引

本页是 vnpy_cta 实盘部署与运维 WIKI 的内容目录。每个页面包含路径链接和单行摘要。

---

## 总览

| 页面 | 摘要 |
|------|------|
| [[overview]] | 系统整体概览：部署拓扑、运行中的策略、关键指标仪表盘 |
| [[architecture]] | 系统架构：组件关系、数据流、技术栈选型 |

---

## 部署

| 页面 | 摘要 |
|------|------|
| [[deployment/vps-setup]] | VPS 服务器选型、初始化配置、安全加固 |
| [[deployment/environment]] | Python 虚拟环境、vnpy 安装、依赖管理 |
| [[deployment/database]] | MongoDB / MySQL / InfluxDB 配置与优化 |
| [[deployment/process-management]] | systemd / supervisor 进程守护配置 |
| [[deployment/network-security]] | 防火墙规则、SSH 加固、API 端口访问控制 |
| [[deployment/deploy-workflow]] | 标准部署流程：从代码到生产环境 |

---

## 运维

| 页面 | 摘要 |
|------|------|
| [[operations/daily-checklist]] | 每日运维检查清单 |
| [[operations/startup-shutdown]] | 系统启停标准操作流程 |
| [[operations/position-reconciliation]] | 持仓对账：系统记录 vs 经纪商记录 |
| [[operations/order-management]] | 订单管理：撤单、改单、人工干预 |
| [[operations/health-checks]] | 系统健康检查项目与判定标准 |

---

## 策略

| 页面 | 摘要 |
|------|------|
| [[strategies/catalog]] | 策略清单：名称、类型、状态、负责人 |
| [[strategies/lifecycle]] | 策略生命周期管理：开发 → 回测 → 模拟盘 → 实盘 |
| [[strategies/configuration]] | 策略参数配置管理：合约、仓位、触发条件 |
| [[strategies/performance]] | 策略绩效分析：夏普比率、最大回撤、胜率 |

---

## 风控

| 页面 | 摘要 |
|------|------|
| [[risk-management/controls]] | 风控框架总览：事前、事中、事后 |
| [[risk-management/position-limits]] | 仓位与净敞口限制规则 |
| [[risk-management/drawdown]] | 回撤控制：阈值、熔断、恢复机制 |
| [[risk-management/black-swan]] | 极端行情预案与应急操作手册 |

---

## 监控

| 页面 | 摘要 |
|------|------|
| [[monitoring/metrics]] | 关键监控指标定义与采集方式 |
| [[monitoring/alerting]] | 告警规则配置与通知渠道（钉钉/微信/邮件） |
| [[monitoring/dashboards]] | Grafana / vnpy 内置面板配置 |
| [[monitoring/logs]] | 日志采集、聚合与查询方案 |

---

## 数据管理

| 页面 | 摘要 |
|------|------|
| [[data-management/market-data]] | 行情数据源接入：CTP / 数据服务商 |
| [[data-management/trade-data]] | 成交、持仓、资金数据的存储与查询 |
| [[data-management/backup]] | 备份策略、备份脚本、恢复演练 |
| [[data-management/retention]] | 数据保留周期与清理策略 |

---

## 故障排查

| 页面 | 摘要 |
|------|------|
| [[troubleshooting/common-issues]] | 高频故障现象与标准处理流程 |
| [[troubleshooting/connection-issues]] | CTP 连接异常：断连、登录失败、行情延迟 |
| [[troubleshooting/order-errors]] | 订单异常：拒单、部分成交、状态不一致 |
| [[troubleshooting/strategy-errors]] | 策略运行时异常：报错、卡顿、信号异常 |
| [[troubleshooting/diagnostic-tools]] | 诊断工具与调试命令汇总 |

---

## 事故记录

| 页面 | 摘要 |
|------|------|
| [[incidents/template]] | 事故报告模板：时间线、影响范围、根因、改进措施 |

---

## 参考资料

| 页面 | 摘要 |
|------|------|
| [[reference/vnpy-docs]] | vnpy 官方文档关键章节索引 |
| [[reference/commands]] | 常用运维命令速查表 |
| [[reference/ctp-specs]] | CTP API 关键接口说明与注意事项 |
| [[reference/external-links]] | 外部资源：社区、博客、工具链 |
