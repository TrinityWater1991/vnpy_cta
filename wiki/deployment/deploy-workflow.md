---
title: "标准部署流程"
category: "deployment"
tags: [deploy, workflow, rollout, rollback, release]
created: 2026-07-16
updated: 2026-07-16
---

# 标准部署流程

> 本文档定义 vnpy CTA 实盘系统的标准部署工作流：代码同步 → 环境检查 → 配置更新 → 重启验证 → 回滚计划。

---

## 部署流程图

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  1. 代码   │     │  2. 环境   │     │  3. 配置   │     │  4. 重启   │     │  5. 验证   │
│  同步     │ ──► │  检查     │ ──► │  更新     │ ──► │  服务     │ ──► │  上线     │
└──────────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
      │               │               │               │               │
      ▼               ▼               ▼               ▼               ▼
  git pull      检查依赖      更新 vt_setting     systemctl      检查日志
  checkout 标签  检查磁盘      更新策略参数      restart        检查持仓
                 检查网络      数据库迁移                         检查订单
                                                                  检查延迟
```

<!-- TODO: 补充完整的部署流程图（含回滚分支和审批环节） -->

---

## 步骤一：代码同步

### 准备工作

```bash
# 进入工作目录
$ cd /opt/vnpy/instance

# 确认当前分支和状态
$ git status
$ git branch

# 拉取最新代码
$ git fetch --all
$ git checkout <目标标签或分支>
$ git pull origin <目标分支>

# 确认同步后的 commit
$ git log --oneline -3
```

### 版本标签管理

| 标签格式 | 示例 | 说明 |
|----------|------|------|
| `v<主版本>.<次版本>.<修订号>` | `v2.1.0` | 正式发布版本 |
| `v<版本>-rc.<序号>` | `v2.1.0-rc.1` | 预发布候选版本 |
| `v<版本>-hotfix.<序号>` | `v2.1.0-hotfix.1` | 紧急修复版本 |

<!-- TODO: 记录当前生产环境的代码版本标签 -->

### 同步确认清单

| 检查项 | 通过条件 | 检查结果 |
|--------|----------|----------|
| 当前分支 | 目标部署分支 | <!-- TODO: 补充 --> |
| commit 一致 | 与测试环境一致 | <!-- TODO: 补充 --> |
| 无未提交修改 | `git status` 干净 | <!-- TODO: 补充 --> |
| 已创建标签 | 版本标签已推送 | <!-- TODO: 补充 --> |

---

## 步骤二：环境检查

### 系统资源检查

```bash
# 磁盘空间
$ df -h /opt/vnpy

# 内存使用
$ free -h

# CPU 负载
$ uptime
$ top -bn1 | head -5

# 网络连通性
$ tcping <CTP_行情_IP> 37789
$ tcping <CTP_交易_IP> 37790
```

### 依赖检查

```bash
# 激活虚拟环境
$ source /opt/vnpy/venv/bin/activate

# 安装/更新依赖
$ pip install -r requirements.txt

# 验证关键模块
$ python -c "import vnpy; print(vnpy.__version__)"
$ python -c "import vnpy_ctp; print('CTP OK')"
```

### 环境检查清单

| 检查项目 | 阈值/要求 | 状态 |
|----------|-----------|------|
| 磁盘使用率 | < 80% | <!-- TODO: 补充 --> |
| 可用内存 | > 2 GB | <!-- TODO: 补充 --> |
| CPU 负载（1min）| < 核心数 * 0.7 | <!-- TODO: 补充 --> |
| CTP 行情连接 | 可连接 | <!-- TODO: 补充 --> |
| CTP 交易连接 | 可连接 | <!-- TODO: 补充 --> |
| 数据库连接 | 可读写 | <!-- TODO: 补充 --> |
| Python 版本 | 3.10.x | <!-- TODO: 补充 --> |
| vnpy 版本 | 符合预期 | <!-- TODO: 补充 --> |

---

## 步骤三：配置更新

### 配置文件管理

```
/opt/vnpy/instance/
├── vt_setting.json          # 主配置文件（数据库、接口等）
├── cta_strategy_setting.json # CTA 策略参数配置
└── .env                     # 敏感信息（密码、Token）
```

### 配置更新流程

```bash
# 备份当前配置
$ cp vt_setting.json vt_setting.json.$(date +%Y%m%d_%H%M%S).bak
$ cp cta_strategy_setting.json cta_strategy_setting.json.$(date +%Y%m%d_%H%M%S).bak

# 更新配置（建议用 diff 检查差异）
$ vim vt_setting.json

# 验证 JSON 格式
$ python -m json.tool vt_setting.json > /dev/null && echo "JSON 格式正确"

# 检查配置差异
$ diff vt_setting.json vt_setting.json.$(date +%Y%m%d_%H%M%S).bak
```

### 配置变更记录

| 变更日期 | 变更内容 | 变更人 | 回滚方式 |
|----------|----------|--------|----------|
| <!-- TODO: 补充 --> | | | |
| <!-- TODO: 补充 --> | | | |

---

## 步骤四：重启服务

### 标准重启流程

```bash
# 方式一：systemd
$ sudo systemctl restart vnpy-trader
$ sudo systemctl status vnpy-trader

# 方式二：supervisor
$ sudo supervisorctl restart vnpy-trader
$ sudo supervisorctl status vnpy-trader

# 检查进程是否正常启动
$ ps aux | grep run_trading
$ ss -tlnp | grep python
```

### 重启后等待时间

| 阶段 | 等待时间 | 检查内容 |
|------|----------|----------|
| 进程启动 | 10 秒 | 进程是否已创建 |
| 连接建立 | 30 秒 | CTP 行情/交易连接是否正常 |
| 数据同步 | 60 秒 | 是否开始接收行情和更新持仓 |
| 策略加载 | 120 秒 | 策略是否全部加载并开始运行 |

<!-- TODO: 确认重启后实际的稳定时间 -->

---

## 步骤五：验证上线

### 验证清单

| 验证项目 | 检查方法 | 通过标准 | 结果 |
|----------|----------|----------|------|
| 进程存活 | `systemctl status vnpy-trader` | active (running) | <!-- TODO: --> |
| 网络连接 | `ss -tlnp \| grep python` | CTP 端口已连接 | <!-- TODO: --> |
| 行情接收 | 查看 vnpy 行情面板 | 最新行情更新时间 < 3s | <!-- TODO: --> |
| 持仓一致 | 对比系统持仓 vs 柜台持仓 | 完全一致 | <!-- TODO: --> |
| 策略运行 | 查看策略状态列表 | 所有策略为"运行中" | <!-- TODO: --> |
| 日志无报错 | `journalctl -u vnpy-trader -n 50` | 无 ERROR 级别日志 | <!-- TODO: --> |
| 交易延迟 | ping CTP 前置机 | < 10ms | <!-- TODO: --> |
| 通知推送 | 检查钉钉/微信群 | 启动通知已收到 | <!-- TODO: --> |

### 回滚判定标准

如出现以下情况之一，立即执行回滚：

| 严重级别 | 现象 | 处理时限 |
|----------|------|----------|
| P0 | 无法连接 CTP 行情或交易 | 5 分钟内 |
| P0 | 策略全部异常终止 | 5 分钟内 |
| P1 | 持仓数据不一致 | 10 分钟内 |
| P1 | 交易延迟超过 50ms | 15 分钟内 |
| P2 | Web 管理界面不可用 | 30 分钟内 |

---

## 回滚计划

### 回滚脚本

```bash
#!/bin/bash
# rollback.sh — 标准回滚脚本

set -e

BACKUP_DIR="/opt/vnpy/deploy-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 回滚代码
git checkout <上一个稳定版本标签>

# 恢复配置文件
cp ${BACKUP_DIR}/vt_setting.json.${PREVIOUS_DEPLOY} /opt/vnpy/instance/vt_setting.json

# 回滚依赖
source /opt/vnpy/venv/bin/activate
pip install -r ${BACKUP_DIR}/requirements.${PREVIOUS_DEPLOY}.txt

# 重启服务
sudo systemctl restart vnpy-trader

# 验证
sleep 30
sudo systemctl status vnpy-trader
```

### 回滚流程

1. **停止部署** — 立即停止当前部署操作
2. **通知团队** — 通过 [[monitoring/alerting]] 配置的通知渠道发送回滚通知
3. **执行回滚** — 运行回滚脚本，恢复到上一个稳定版本
4. **验证恢复** — 使用步骤五的验证清单确认系统正常运行
5. **根因分析** — 排查部署失败原因，记录到 [[incidents/template]]
6. **复盘改进** — 更新测试流程，防止同类问题再次发生

### 部署物料保存

每次部署应保存以下物料，保存周期为 30 天：

| 物料 | 路径 | 用途 |
|------|------|------|
| 代码版本标签 | git tag | 精确回溯代码状态 |
| 配置文件备份 | `deploy-backups/` | 回滚时恢复配置 |
| 依赖冻结文件 | `deploy-backups/requirements-*.txt` | 回滚时恢复依赖 |
| 部署日志 | 本页下方的部署记录表 | 审计和复盘 |
| 验证结果 | 步骤五的验证清单 | 审计和复盘 |

---

## 部署记录

| 日期 | 版本 | 部署人 | 变更摘要 | 结果 | 备注 |
|------|------|--------|----------|------|------|
| <!-- TODO: 记录首次部署 --> | | | | | |
| <!-- TODO: 记录下次部署 --> | | | | | |

---

## 相关页面

- [[deployment/vps-setup]] — VPS 服务器基础配置
- [[deployment/environment]] — Python 环境与依赖管理
- [[deployment/database]] — 数据库配置迁移
- [[deployment/process-management]] — 进程启停与守护配置
- [[deployment/network-security]] — 网络配置变更
- [[operations/startup-shutdown]] — 系统启停标准操作流程
- [[operations/health-checks]] — 健康检查验证
- [[incidents/template]] — 事故报告模板
- [[reference/commands]] — 部署常用命令速查
