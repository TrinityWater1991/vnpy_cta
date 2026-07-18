---
title: "操作日志"
category: "reference"
tags: [log, changelog]
created: 2026-07-16
updated: 2026-07-16
---

# 操作日志

本文件按时间倒序记录 WIKI 的所有变更。每次 Ingest、Query 归档、Lint、事故复盘后追加一条记录。

**格式**: `## [YYYY-MM-DD] 操作类型 | 标题`

**操作类型**: `ingest` | `query` | `lint` | `incident`

---

## [2026-07-18] ingest | 学习 vnpy 官方 no_ui/run.py 并重构项目

参考 [官方 examples/no_ui/run.py](https://github.com/vnpy/vnpy/blob/master/examples/no_ui/run.py) 重构系统：

- `run_headless.py` 重写：采用官方 `init_engine()` → `init_all_strategies()` → `sleep(60)` → `start_all_strategies()` 启动序列
- 添加 `LogEngine` + `EVENT_CTA_LOG` 事件注册，实现结构化日志
- 网关改为动态加载（占位 Bitget，待开发完成后接入）
- 修复策略类注册问题：`init_engine()` 内部 `load_strategy_class()` 扫描策略模块并填充 `self.classes`，不调用则 `add_strategy()` 找不到类
- 移除 `dual_ma.py`（依赖 matplotlib，非实盘策略）
- 更新 [[architecture]]：补充初始化流程序列图、进程管理分层、数据流

## [2026-07-16] ingest | 创建部署分类全套页面

填充 6 篇部署类 WIKI 页面的详细内容：

- [[deployment/vps-setup]] — VPS 规格、SSH 加固、ufw 防火墙、fail2ban、系统安全基线
- [[deployment/environment]] — Python 版本管理、venv、vnpy 安装、依赖冻结与验证
- [[deployment/database]] — SQLite 主方案、MongoDB/MySQL 备选方案、索引优化、备份策略
- [[deployment/process-management]] — systemd unit 文件、supervisor 配置、进程健康检查、多实例管理
- [[deployment/network-security]] — 网络拓扑、iptables/ufw 规则、CTP 网络要求、API 端口防护、VPN 方案
- [[deployment/deploy-workflow]] — 5 步标准流程（同步→检查→配置→重启→验证）、回滚脚本、部署记录表

## [2026-07-16] scaffold | WIKI 目录结构初始化

创建 WIKI 目录结构和所有页面模板。详见 [[WIKI_SCHEMA]]。

新建页面：
- [[index]] — 内容目录
- [[log]] — 本文件
- [[overview]] — 系统总览
- [[architecture]] — 系统架构
- 部署：[[deployment/vps-setup]], [[deployment/environment]], [[deployment/database]], [[deployment/process-management]], [[deployment/network-security]], [[deployment/deploy-workflow]]
- 运维：[[operations/daily-checklist]], [[operations/startup-shutdown]], [[operations/position-reconciliation]], [[operations/order-management]], [[operations/health-checks]]
- 策略：[[strategies/catalog]], [[strategies/lifecycle]], [[strategies/configuration]], [[strategies/performance]]
- 风控：[[risk-management/controls]], [[risk-management/position-limits]], [[risk-management/drawdown]], [[risk-management/black-swan]]
- 监控：[[monitoring/metrics]], [[monitoring/alerting]], [[monitoring/dashboards]], [[monitoring/logs]]
- 数据：[[data-management/market-data]], [[data-management/trade-data]], [[data-management/backup]], [[data-management/retention]]
- 排障：[[troubleshooting/common-issues]], [[troubleshooting/connection-issues]], [[troubleshooting/order-errors]], [[troubleshooting/strategy-errors]], [[troubleshooting/diagnostic-tools]]
- 事故：[[incidents/template]]
- 参考：[[reference/vnpy-docs]], [[reference/commands]], [[reference/ctp-specs]], [[reference/external-links]]
