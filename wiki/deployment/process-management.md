---
title: "进程管理与守护配置"
category: "deployment"
tags: [systemd, supervisor, daemon, process, service, restart]
created: 2026-07-16
updated: 2026-07-16
---

# 进程管理与守护配置

> 本文档说明使用 systemd 和 supervisor 管理 vnpy CTA 实盘进程的配置方法，包括开机自启、异常重启、日志管理等。

---

## 方案选型

| 特性 | systemd | supervisor |
|------|---------|------------|
| 集成度 | 操作系统原生 | 第三方，需额外安装 |
| 配置复杂度 | 中等 | 简单 |
| 进程监控 | 自带重启策略 | 自带重启策略 |
| 日志管理 | journald | 自带日志轮转 |
| Web 管理界面 | 无 | 可选 Web UI |
| 子进程管理 | 需 Cgroup 配置 | 自动管理子进程 |

### 选择建议

| 场景 | 推荐方案 | 原因 |
|------|----------|------|
| 单进程实盘 | systemd | 原生集成，无需额外依赖 |
| 多进程/多策略 | supervisor | 统一管理多组进程 |
| 混合使用 | systemd + supervisor | systemd 托底，supervisor 管理 vnpy 进程组 |

<!-- TODO: 确认生产环境实际使用的进程管理方案 -->

---

## systemd 配置

### Service Unit 文件

创建文件 `/etc/systemd/system/vnpy-trader.service`：

```ini
[Unit]
Description=vnpy CTA Trading Service
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=trader
Group=trader
WorkingDirectory=/opt/vnpy/instance

# 激活虚拟环境并启动主程序
ExecStart=/opt/vnpy/venv/bin/python /opt/vnpy/run_trading.py

# 重启策略
Restart=always
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vnpy-trader

# 资源限制
LimitNOFILE=65535
LimitNPROC=65535
MemoryMax=4G
CPUQuota=80%

# 安全加固
ProtectSystem=full
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
```

<!-- TODO: 确认 ExecStart 实际使用的主程序路径和文件名 -->
<!-- TODO: 根据服务器实际性能调整 MemoryMax 和 CPUQuota 参数 -->

### 常用命令

```bash
# 启动服务
$ sudo systemctl start vnpy-trader

# 停止服务
$ sudo systemctl stop vnpy-trader

# 重启服务
$ sudo systemctl restart vnpy-trader

# 查看状态
$ sudo systemctl status vnpy-trader

# 查看实时日志
$ sudo journalctl -fu vnpy-trader

# 查看最近 N 行日志
$ sudo journalctl -u vnpy-trader -n 100

# 设置开机自启
$ sudo systemctl enable vnpy-trader

# 禁用开机自启
$ sudo systemctl disable vnpy-trader

# 重新加载 Unit 文件（修改后）
$ sudo systemctl daemon-reload
```

### 重启策略说明

| 参数 | 值 | 含义 |
|------|-----|------|
| `Restart` | always | 无论退出码如何，总是自动重启 |
| `RestartSec` | 10 | 重启前等待 10 秒 |
| `StartLimitIntervalSec` | 300 | 5 分钟内超过以下次数则不再重启 |
| `StartLimitBurst` | 5 | 300 秒内最多重试 5 次 |

---

## supervisor 配置

### 安装

```bash
$ sudo apt install supervisor
$ sudo systemctl enable supervisor
$ sudo systemctl start supervisor
```

### 程序配置

创建文件 `/etc/supervisor/conf.d/vnpy-trader.conf`：

```ini
[program:vnpy-trader]
command=/opt/vnpy/venv/bin/python /opt/vnpy/run_trading.py
directory=/opt/vnpy/instance
user=trader
group=trader
numprocs=1
autostart=true
autorestart=true
startsecs=10
startretries=5
exitcodes=0,2
stopsignal=TERM
stopwaitsecs=30

# 环境变量
environment=
    PYTHONUNBUFFERED=1,
    VNPY_LOG_DIR=/var/log/vnpy

# 日志配置
stdout_logfile=/var/log/vnpy/trader-stdout.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
stderr_logfile=/var/log/vnpy/trader-stderr.log
stderr_logfile_maxbytes=50MB
stderr_logfile_backups=10
```

### 常用命令

```bash
# 重载配置
$ sudo supervisorctl reread
$ sudo supervisorctl update

# 启动/停止/重启
$ sudo supervisorctl start vnpy-trader
$ sudo supervisorctl stop vnpy-trader
$ sudo supervisorctl restart vnpy-trader

# 查看状态
$ sudo supervisorctl status vnpy-trader

# 查看所有进程
$ sudo supervisorctl status

# 查看实时日志
$ sudo supervisorctl tail -f vnpy-trader
```

<!-- TODO: 补充 supervisor 实际配置中使用的日志路径 -->
<!-- TODO: 补充 supervisor Web 管理界面配置（如需） -->

---

## 进程健康检查

### 检查清单

| 检查项目 | 命令 | 正常状态 |
|----------|------|----------|
| 进程运行状态 | `systemctl status vnpy-trader` | active (running) |
| 进程是否存活 | `ps aux \| grep run_trading` | 进程存在 |
| 监听的端口 | `ss -tlnp \| grep python` | 预期端口已监听 |
| 内存使用率 | `ps -o pid,rss,cmd -p <PID>` | < 4GB |
| CPU 使用率 | `top -b -n1 -p <PID>` | < 80% |
| 文件描述符 | `ls /proc/<PID>/fd \| wc -l` | < 65535 |

<!-- TODO: 补充自动化健康检查脚本路径和告警机制 -->

---

## 多实例管理

如需在同一台机器上运行多个策略实例，可使用以下配置：

### systemd 多实例模板

```ini
[Unit]
Description=vnpy CTA Strategy Instance %i
After=network.target

[Service]
Type=simple
User=trader
WorkingDirectory=/opt/vnpy/instances/instance-%i
ExecStart=/opt/vnpy/venv/bin/python /opt/vnpy/run_trading.py --config config_%i.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 启用多个实例
$ sudo systemctl enable vnpy-strategy@cta1
$ sudo systemctl enable vnpy-strategy@cta2
$ sudo systemctl start vnpy-strategy@cta1
$ sudo systemctl start vnpy-strategy@cta2
```

<!-- TODO: 确认是否需要多实例部署 -->

---

## 相关页面

- [[deployment/deploy-workflow]] — 标准部署流程中的启停步骤
- [[operations/startup-shutdown]] — 系统启停标准操作流程
- [[operations/health-checks]] — 系统健康检查项目
- [[monitoring/alerting]] — 进程异常告警配置
- [[troubleshooting/common-issues]] — 进程管理相关常见问题
