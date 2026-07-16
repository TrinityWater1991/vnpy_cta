---
title: "系统启停流程"
category: "operations"
tags: [startup, shutdown, procedure, systemd]
created: 2026-07-16
updated: 2026-07-16
---

# 系统启停流程

> 本页定义 CTA 实盘系统的标准启动和关闭操作流程，涵盖日常启停及异常场景处理。

## 前置条件

### 环境信息

| 项目 | 说明 | 参考 |
|------|------|------|
| 操作系统 | Ubuntu 22.04 LTS | |
| 运行用户 | vnpy | |
| 工作目录 | `/home/vnpy/vnpy_cta` | |
| 进程管理 | systemd | [[../deployment/process-management]] |
| Python 环境 | conda / venv | [[../deployment/environment]] |

### 依赖组件检查

- [ ] MySQL / MongoDB 服务运行中
- [ ] Redis 服务运行中（如使用）
- [ ] CTP 行情服务可用性确认
- [ ] 网络连通性确认（参见 [[../troubleshooting/connection-issues]]）

<!-- TODO: 补充实际部署中的数据库地址和端口 -->
<!-- TODO: 添加各依赖服务的心跳检测命令 -->

## 启动流程 (Startup)

### 标准启动步骤

```bash
# 1. 检查前置服务状态
$ systemctl status mysql      # 或 mongod
$ systemctl status redis

# 2. 检查系统资源
$ df -h
$ free -h

# 3. 启动 CTA 系统
$ systemctl start vnpy-cta

# 4. 确认启动成功
$ systemctl status vnpy-cta
$ journalctl -u vnpy-cta -n 30 --no-pager
```

### 启动确认清单

| 步骤 | 检查项 | 验证方式 | 通过标准 |
|------|--------|----------|----------|
| 1 | 数据库连接 | 查看启动日志 | "Database connected" 日志出现 |
| 2 | CTP 行情连接 | vnpy 日志 | "Login success - Market" 出现 |
| 3 | CTP 交易连接 | vnpy 日志 | "Login success - Trade" 出现 |
| 4 | 合约加载 | vnpy 日志 | 所有合约加载完成 |
| 5 | 策略初始化 | vnpy 界面 / API | 策略状态 = "Running" |
| 6 | 行情推送 | 检查最新 Tick | 行情时间 < 当前时间 3s |
| 7 | 订单路由 | 模拟单测试 | 下单 / 撤单正常 |

<!-- TODO: 补充 vnpy 启动时的详细日志路径 -->
<!-- TODO: 添加 CTP 登录失败的重试逻辑与等待时间建议 -->
<!-- TODO: 补充 -- 模拟单测试的具体操作脚本 -->

### 启动失败处理

| 故障现象 | 可能原因 | 处理步骤 |
|----------|----------|----------|
| CTP 登录失败 | 网络问题 / 账号密码错误 | 检查网络 → 验证配置 → 重试，参见 [[../troubleshooting/connection-issues]] |
| 数据库连接失败 | 数据库未启动 / 配置错误 | `systemctl start mysql` → 验证配置 |
| 策略初始化异常 | 策略代码错误 / 参数异常 | 查看堆栈 → 修复 → 重启，参见 [[../troubleshooting/strategy-errors]] |
| 合约加载不全 | 合约配置缺失 | 检查 `vt_setting.json` 合约列表 |

## 关闭流程 (Shutdown)

### 标准关闭步骤

```bash
# 1. 通知相关人员（群消息 / 邮件）
# 2. 确认无未处理订单
# 3. 停止 CTA 系统
$ systemctl stop vnpy-cta

# 4. 确认进程已终止
$ systemctl status vnpy-cta
$ ps aux | grep python
```

### 关闭确认清单

| 步骤 | 检查项 | 验证方式 | 通过标准 |
|------|--------|----------|----------|
| 1 | 未成交订单 | 查询柜台接口 | 无 Pending / 部分成交订单 |
| 2 | 策略平仓状态 | 检查持仓 | 已按计划平仓（如需要） |
| 3 | 数据持久化 | 查看日志 | "Data saved" 或类似确认 |
| 4 | 进程终止 | `systemctl status` | Active: inactive (dead) |
| 5 | 资源释放 | `lsof -i:交易端口` | 端口已释放 |

<!-- TODO: 补充紧急关停场景下的操作步骤 -->
<!-- TODO: 添加交易时段内不可关机的约束说明 -->

### 紧急关闭 (Emergency Shutdown)

适用于极端行情、系统异常、网络攻击等场景。

```bash
# 强制停止（60s 超时后 SIGKILL）
$ systemctl kill -s SIGTERM vnpy-cta
# 或直接 kill 进程
$ pkill -f vnpy_cta
```

| 场景 | 操作 | 后续处理 |
|------|------|----------|
| 策略失控 (无限下单) | 关闭交易网关 → 切手动 | 检查订单 → 撤销 → 复盘 |
| 行情异常 (数据错误) | 断开 CTP 行情 → 重启 | 确认数据源正常后恢复 |
| 服务器宕机 | 云平台强制重启 | 自启动策略 → 检查一致性和 [[position-reconciliation]] |

## 定时自动启停

如使用 cron 或 systemd timer 实现自动启停，配置示例如下：

```bash
# crontab 示例：自动启动（08:40 盘前）
40 8 * * 1-5 /usr/bin/systemctl start vnpy-cta

# crontab 示例：自动关闭（15:30 收盘后）
30 15 * * 1-5 /usr/bin/systemctl stop vnpy-cta
```

<!-- TODO: 补充系统节假日交易日历配置 -->
<!-- TODO: 添加自动启停的日志记录与通知机制 -->
<!-- TODO: 讨论非交易日的系统维护窗口期安排 -->

## 相关页面

- [[daily-checklist]] — 每日检查清单
- [[health-checks]] — 健康检查项目与判定标准
- [[../deployment/process-management]] — 进程管理配置
- [[../deployment/deploy-workflow]] — 部署流程
- [[position-reconciliation]] — 持仓对账（重启后必做）
