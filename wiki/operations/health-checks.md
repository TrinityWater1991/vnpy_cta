---
title: "系统健康检查"
category: "operations"
tags: [health-check, process, resource, monitoring]
created: 2026-07-16
updated: 2026-07-16
---

# 系统健康检查

> 本页定义 CTA 实盘系统的健康检查项目与判定标准，涵盖进程级、功能级、资源级三个层次。

## 检查层级概览

| 层级 | 检查对象 | 检查频率 | 自动化程度 |
|------|----------|----------|------------|
| 进程级 | 操作系统进程、systemd 服务 | 每分钟 | 完全自动化 |
| 功能级 | CTP 连接、策略运行、行情推送 | 每 30 秒 | 完全自动化 |
| 资源级 | CPU、内存、磁盘、网络 | 每分钟 | 完全自动化 |
| 业务级 | 持仓一致性、订单执行率、策略P&L | 每日 | 半自动化 |

<!-- TODO: 补充实际环境中的监控部署方案（Grafana / Prometheus / 自建） -->
<!-- TODO: 添加健康检查结果的 API 输出格式设计 -->

## 进程级健康检查

检查操作系统层面各组件的存活状态。

```bash
# 检查 vnpy 主进程
$ systemctl is-active vnpy-cta
# 输出: active / inactive / failed

# 检查所有相关进程
$ ps aux | grep -E "vnpy|python|ctp"
```

| 组件 | 进程名 | 检查命令 | 健康标准 |
|------|--------|----------|----------|
| CTA 交易系统 | vnpy-cta | `systemctl status vnpy-cta` | active (running) |
| 数据库 | mongod / mysqld | `systemctl status mongod` | active (running) |
| 行情网关 | (集成在 vnpy 内) | `ps aux | grep ctp` | 进程存在 |
| 日志采集 | rsyslog / journald | `systemctl status rsyslog` | active (running) |
| SSH 服务 | sshd | `systemctl status sshd` | active (running) |

### 进程异常处理

| 异常现象 | 可能原因 | 自动恢复 | 人工处理 |
|----------|----------|----------|----------|
| 进程崩溃 (crashed) | 代码异常 / OOM | systemd 自动重启 | 检查 crash 日志 → 修复后重启 |
| 进程挂起 (hung) | 死锁 / 死循环 | Watchdog 超时重启 | 分析线程堆栈 → 修复 |
| 频繁重启 (flapping) | 启动条件不满足 | 停止自动重启 | 检查依赖 → 手动启动 |
| Zombie 进程 | 子进程未回收 | 无 | `kill -9` 清理 |

<!-- TODO: 补充 OOM 保护的内存限制配置 -->
<!-- TODO: 添加 systemd watchdog 的具体配置参数 -->

## 功能级健康检查

检查系统核心功能是否正常运行。

### CTP 连接状态

| 检查项 | 检查方式 | 正常 | 警告 | 严重 |
|--------|----------|------|------|------|
| 行情通道 | 查询 Gateway 连接状态 | 已连接 | 重连中 > 30s | 断开 > 60s |
| 交易通道 | 查询 Gateway 连接状态 | 已连接 | 重连中 > 30s | 断开 > 60s |
| 心跳延迟 | CTP 心跳报文时间差 | < 3s | 3-10s | > 10s |
| 行情刷新 | 最后 Tick 时间 | < 1s | 1-5s | > 5s |

### 策略运行状态

| 检查项 | 检查方式 | 正常 | 异常 |
|--------|----------|------|------|
| 策略进程 | `get_strategy_status()` | Running | Stopped / Error |
| 策略交易信号 | 查询信号队列 | 正常排队 | 信号堆积 > 50 |
| 策略参数 | 对比配置快照 | 与预期一致 | 参数被篡改 |
| 策略运行时长 | 查询启动时间 | 交易日全程运行 | 盘中重启过 |

<!-- TODO: 补充策略信号堆积的阈值配置说明 -->
<!-- TODO: 添加策略参数的版本快照机制 -->

### 核心功能自检

```python
# 健康检查脚本伪代码
def health_check():
    checks = {
        "ctp_market_connected": check_ctp_market(),
        "ctp_trade_connected": check_ctp_trade(),
        "strategies_running": check_strategies(),
        "tick_freshness": check_tick_freshness(max_lag=3),
        "order_queue_empty": check_order_queue(max_pending=10),
        "position_consistent": quick_position_check(),
    }
    return {k: ("PASS" if v else "FAIL") for k, v in checks.items()}
```

<!-- TODO: 实现完整的健康检查脚本 `/usr/local/bin/vnpy-health-check` -->

## 资源级健康检查

### 系统资源

| 资源 | 检查命令 | 正常 | 警告 | 严重 |
|------|----------|------|------|------|
| CPU 使用率 | `top -bn1 \| grep Cpu` | < 50% | 50-80% | > 80% |
| 内存使用率 | `free -m \| grep Mem` | < 60% | 60-80% | > 80% |
| 磁盘使用率 (/) | `df -h /` | < 60% | 60-80% | > 80% |
| 磁盘使用率 (/data) | `df -h /data` | < 60% | 60-80% | > 80% |
| 磁盘 IO | `iostat -x 1 3` | util < 50% | 50-80% | > 80% |
| 网络带宽 | `iftop -t -s 3` | 使用率 < 30% | 30-60% | > 60% |
| Swap 使用率 | `free -m \| grep Swap` | 0 | < 20% | > 20% |
| 文件描述符 | `lsof \| wc -l` | < 50%上限 | 50-80%上限 | > 80%上限 |

<!-- TODO: 补充各资源指标的采��脚本和告警配置 -->
<!-- TODO: 添加历史基线值与当前值的对比分析 -->

### 数据库资源

| 检查项 | 检查方式 | 正常 | 严重 |
|--------|----------|------|------|
| 连接数 | `mongo --eval "db.serverStatus().connections"` | < 80%上限 | > 80%上限 |
| 查询延迟 | 执行基准查询 | < 100ms | > 500ms |
| 数据文件大小 | `du -sh /var/lib/mongodb` | 正常增长 | 磁盘即将打满 |
| 复制延迟 (如有) | `rs.status()` | < 1s | > 10s |

## 自动健康检查脚本

```bash
#!/bin/bash
# vnpy-health-check.sh — 一键健康检查脚本

echo "=== 进程级 ==="
systemctl is-active vnpy-cta || echo "FAIL: vnpy-cta not running"

echo "=== 资源级 ==="
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d. -f1)
[ "$CPU" -lt 80 ] && echo "PASS: CPU $CPU%" || echo "FAIL: CPU $CPU%"

MEM=$(free -m | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
[ "$MEM" -lt 80 ] && echo "PASS: MEM $MEM%" || echo "FAIL: MEM $MEM%"

DISK=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%')
[ "$DISK" -lt 80 ] && echo "PASS: DISK $DISK%" || echo "FAIL: DISK $DISK%"

echo "=== 功能级 ==="
journalctl -u vnpy-cta -n 20 --no-pager | grep -q "ERROR" && echo "WARN: Error in logs"
```

<!-- TODO: 将此脚本部署到 /usr/local/bin/ 并设置定时执行 -->

## 告警通知设置

| 检查层级 | 告警条件 | 通知方式 | 响应时间 |
|----------|----------|----------|----------|
| 进程级 | 进程停止 / 崩溃 | 钉钉 / 短信 | 1 分钟内 |
| 功能级 | CTP 断开 / 策略停止 | 钉钉 / 电话 | 3 分钟内 |
| 资源级 | CPU/内存/磁盘超限 | 钉钉 | 5 分钟内 |
| 业务级 | 持仓差异 / 连续亏损 | 邮件 + 电话 | 30 分钟内 |

参见 [[../monitoring/alerting]] 获取详细告警规则配置。

## 相关页面

- [[daily-checklist]] — 每日检查清单（盘前/盘中/盘后各阶段的检查场景）
- [[startup-shutdown]] — 系统启停流程
- [[../monitoring/metrics]] — 关键监控指标定义
- [[../monitoring/alerting]] — 告警规则配置
- [[../monitoring/dashboards]] — 监控面板配置
- [[../deployment/process-management]] — 进程管理配置
- [[../troubleshooting/common-issues]] — 常见故障处理
