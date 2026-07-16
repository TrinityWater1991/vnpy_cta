# WIKI Schema

本文件定义了 vnpy_cta 实盘部署与运维 WIKI 的结构、约定和工作流。LLM 在摄取新信息、回答查询、维护 WIKI 时应遵循此 Schema。

---

## 目录结构

```
wiki/
├── WIKI_SCHEMA.md          # 本文件 — WIKI 的结构与维护约定
├── index.md                # 内容目录 — 所有页面的分类索引（含单行摘要）
├── log.md                  # 操作日志 — 按时间追加的 WIKI 变更记录
├── overview.md             # 系统总览 — 整体架构、部署拓扑、关键指标摘要
├── architecture.md         # 系统架构 — 组件关系、数据流、技术栈
├── deployment/             # 部署相关
│   ├── vps-setup.md        #   VPS 服务器配置
│   ├── environment.md      #   Python / vnpy 运行环境
│   ├── database.md         #   数据库配置（MongoDB / MySQL / InfluxDB）
│   ├── process-management.md # 进程管理（systemd / supervisor）
│   ├── network-security.md #   网络安全与访问控制
│   └── deploy-workflow.md  #   标准部署流程
├── operations/             # 运维操作
│   ├── daily-checklist.md  #   每日检查清单
│   ├── startup-shutdown.md #   启停流程
│   ├── position-reconciliation.md # 持仓对账
│   ├── order-management.md #   订单管理与人工干预
│   └── health-checks.md    #   健康检查
├── strategies/             # 策略管理
│   ├── catalog.md          #   策略清单
│   ├── lifecycle.md        #   策略生命周期（开发→回测→模拟→实盘）
│   ├── configuration.md    #   策略参数配置
│   └── performance.md      #   策略绩效分析
├── risk-management/        # 风险管理
│   ├── controls.md         #   风控框架
│   ├── position-limits.md  #   仓位与敞口限制
│   ├── drawdown.md         #   回撤控制
│   └── black-swan.md       #   极端行情与应急处理
├── monitoring/             # 监控告警
│   ├── metrics.md          #   关键指标定义
│   ├── alerting.md         #   告警规则与通知渠道
│   ├── dashboards.md       #   监控面板
│   └── logs.md             #   日志采集与分析
├── data-management/        # 数据管理
│   ├── market-data.md      #   行情数据接入
│   ├── trade-data.md       #   交易数据存储
│   ├── backup.md           #   备份策略与恢复
│   └── retention.md        #   数据保留策略
├── troubleshooting/        # 故障排查
│   ├── common-issues.md    #   常见问题汇总
│   ├── connection-issues.md #  CTP / 网络连接问题
│   ├── order-errors.md     #   订单错误排查
│   ├── strategy-errors.md  #   策略运行时错误
│   └── diagnostic-tools.md #   诊断工具与命令
├── incidents/              # 事故记录
│   └── template.md         #   事故报告模板
└── reference/              # 参考资料
    ├── vnpy-docs.md        #   vnpy 官方文档索引
    ├── commands.md         #   常用命令速查
    ├── ctp-specs.md        #   CTP 接口要点
    └── external-links.md   #   外部资源链接
```

---

## 页面约定

### 元数据（Frontmatter）

每个 WIKI 页面顶部必须包含 YAML frontmatter：

```yaml
---
title: "页面标题"
category: "deployment | operations | strategies | risk-management | monitoring | data-management | troubleshooting | incidents | reference"
tags: [keyword1, keyword2]
created: 2026-07-16
updated: 2026-07-16
---
```

- `title`: 页面标题，与 index.md 中的标题一致
- `category`: 所属分类，对应子目录名
- `tags`: 跨分类的标签，便于关联搜索
- `created`: 创建日期
- `updated`: 最后更新日期（每次修改都更新）

### 交叉引用

- 页面之间使用 `[[page-name]]` 进行 WikiLink 引用
- 引用同一目录下的页面：`[[page-name]]`
- 引用其他目录下的页面：`[[../category/page-name]]`
- 在 index.md 中注明每个页面的入链和出链情况

### 内容风格

- 使用中文撰写
- 代码块标注语言类型
- 配置示例使用实际部署中的参数（敏感信息脱敏）
- 命令行示例使用 `$` 前缀
- 表格用于对比和清单类信息

---

## 工作流

### Ingest — 摄取新信息

触发条件：用户提供了新的信息源（文章、日志、配置变更、操作经验等），或说「记录到 WIKI」。

LLM 应执行的步骤：

1. **读取源信息**，识别关键知识点
2. **确定影响范围**：影响哪些已有页面？需要新建页面吗？与已有内容有矛盾吗？
3. **更新 index.md**：新增页面登记到对应分类；已有页面摘要如有变化则更新
4. **更新受影响页面**：在相关页面中追加或修正内容
5. **追加 log.md**：记录本次操作（时间、类型、摘要）
6. **反馈给用户**：报告更新了哪些页面，标出需要注意的矛盾或 Gap

### Query — 回答查询

触发条件：用户提出关于部署/运维的问题。

LLM 应执行的步骤：

1. **先读 index.md**：定位相关页面
2. **精读相关页面**：获取详细信息
3. **合成回答**：带引用来源（`[[page-name]]` 链接）
4. **可选归档**：如果回答有长期价值，提出「要不要把这段分析归档到 WIKI？」

### Lint — 健康检查

触发条件：用户说「检查 WIKI」或定期触发。

LLM 应检查：

- [ ] 页面间矛盾：不同页面对同一事物的描述是否冲突
- [ ] 过期内容：是否有已被新信息取代的旧说法
- [ ] 孤立页面：是否有入链为 0 的页面（orphan）
- [ ] 缺失覆盖：是否有重要概念被多次提及但没有独立页面
- [ ] 缺失交叉引用：相关内容是否互相链接
- [ ] frontmatter 一致性：所有页面是否有正确的 frontmatter
- [ ] 信息缺口：哪些关键信息缺失，可以建议用户补充

---

## 特殊文件说明

### index.md

- 按 category 分组列出所有页面
- 每个页面包含：`[[页面路径]]` + 单行摘要
- 可选标注：创建日期、标签数、入链数
- 在每次 Ingest 后更新

### log.md

- 按时间倒序追加
- 每条记录格式：`## [YYYY-MM-DD] 操作类型 | 标题`
- 操作类型：`ingest` | `query` | `lint` | `incident`
- 记录中引用受影响的页面

### overview.md

- 系统整体情况的浓缩摘要
- 应包含：当前部署拓扑、运行中的策略列表、最近 7 天关键指标
- 每次重大变更后更新

---

## Co-evolution 约定

本 Schema 应随着 WIKI 的使用逐步演进：

- 用户觉得某个分类不合适 → 调整目录结构
- 用户需要新的页面类型 → 更新 Schema
- 用户发现更好的 cross-reference 约定 → 更新 Schema
- 每次 Schema 变更后，LLM 应检查是否需要批量更新已有页面
