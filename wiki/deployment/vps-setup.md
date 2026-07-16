---
title: "VPS 服务器配置"
category: "deployment"
tags: [vps, server, ssh, firewall, fail2ban, security]
created: 2026-07-16
updated: 2026-07-16
---

# VPS 服务器配置

> 本文档记录 vnpy CTA 实盘运行所需的 VPS 服务器选型标准、初始化配置与安全加固步骤。

---

## 硬件规格

### 推荐配置

| 配置项 | 最低要求 | 推荐配置 | 说明 |
|--------|----------|----------|------|
| CPU | 2 核 | 4 核 | CTP 行情计算与策略运算需求 |
| 内存 | 4 GB | 8 GB | vnpy + MongoDB/Redis 开销 |
| 系统盘 | 40 GB SSD | 80 GB SSD | 日志、数据文件、备份占用 |
| 带宽 | 5 Mbps | 10 Mbps+ | CTP 行情数据流与交易延迟要求 |
| 操作系统 | Ubuntu 20.04 | Ubuntu 22.04 LTS | 长期支持版本，vnpy 兼容性最佳 |

<!-- TODO: 确认实际使用的云服务商和具体实例规格 -->

### 服务商对比

| 服务商 | 优势 | 劣势 | 实盘使用情况 |
|--------|------|------|-------------|
| 阿里云 ECS | 国内节点多，延迟低 | 价格较高 | <!-- TODO: 补充 --> |
| 腾讯云 CVM | 与 CTP 机房互联好 | 部分机型性能偏低 | <!-- TODO: 补充 --> |
| AWS EC2 | 全球覆盖，稳定性好 | 国内网络延迟不稳定 | <!-- TODO: 补充 --> |
| 华为云 | 金融行业合规 | 生态不如前两者 | <!-- TODO: 补充 --> |

<!-- TODO: 填写实际使用的服务商、实例类型与月费用 -->

---

## SSH 安全加固

### 初始配置

```bash
# 创建非 root 用户
$ adduser trader
$ usermod -aG sudo trader

# 上传公钥
$ mkdir -p /home/trader/.ssh
$ chmod 700 /home/trader/.ssh
$ echo "<your-public-key>" >> /home/trader/.ssh/authorized_keys
$ chmod 600 /home/trader/.ssh/authorized_keys
$ chown -R trader:trader /home/trader/.ssh
```

### SSH 守护进程配置 (`/etc/ssh/sshd_config`)

```bash
# 安全加固项
Port 2222                              # 修改默认端口，避免扫描攻击
PermitRootLogin no                     # 禁用 root 远程登录
PubkeyAuthentication yes               # 仅允许密钥认证
PasswordAuthentication no              # 禁用密码登录
AllowUsers trader                      # 仅允许指定用户 SSH 登录
MaxAuthTries 3                         # 最大认证尝试次数
ClientAliveInterval 300                # 客户端保活间隔（秒）
ClientAliveCountMax 2                  # 保活探测最大失败次数
```

<!-- TODO: 记录实际使用的 SSH 端口号 -->

### SSH 密钥管理

| 项目 | 内容 |
|------|------|
| 密钥类型 | Ed25519（推荐）/ RSA 4096 |
| 密钥生成命令 | `ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519_vnpy` |
| 密钥存储位置 | <!-- TODO: 补充密钥备份位置（密码管理器/密钥管理服务） --> |
| 轮换周期 | <!-- TODO: 补充密钥轮换周期 --> |

---

## 防火墙配置

使用 `ufw` 管理防火墙规则：

```bash
# 安装并启用 ufw
$ apt install ufw
$ ufw default deny incoming
$ ufw default allow outgoing

# 开放必要端口
$ ufw allow 2222/tcp                   # SSH（按实际端口修改）
$ ufw allow 37789/tcp                  # CTP 行情端口
$ ufw allow 37790/tcp                  # CTP 交易端口
$ ufw allow 8080/tcp                   # vnpy Web 管理（内网专用）
$ ufw allow 8001/tcp                   # 可选：REST API（内网专用）

# 启用防火墙
$ ufw enable
$ ufw status verbose
```

<!-- TODO: 根据实际 CTP 前置机地址添加 IP 白名单规则 -->
<!-- TODO: 确认是否需要开放其他端口（监控系统、VPN 等） -->

---

## fail2ban 配置

### 安装与基础配置

```bash
$ apt install fail2ban
$ cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
```

### SSH 防护规则 (`/etc/fail2ban/jail.local`)

```ini
[sshd]
enabled = true
port    = 2222
filter  = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime  = 3600
findtime = 600
```

| 参数 | 值 | 说明 |
|------|-----|------|
| maxretry | 3 | 最大重试次数 |
| bantime | 3600 | 封禁时长（秒），初次 1 小时 |
| findtime | 600 | 统计窗口（秒），此时间内达到 maxretry 则封禁 |
| bantime.increment | true | 重复违规时逐步增加封禁时间 |

<!-- TODO: 确认 fail2ban 是否已启用并配置告警通知 -->

---

## 系统安全基线

### 自动安全更新

```bash
$ apt install unattended-upgrades
$ dpkg-reconfigure --priority=low unattended-upgrades
```

### 内核参数优化

```bash
# /etc/sysctl.d/99-vnpy-network.conf

# 网络连接优化
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_tw_reuse = 1

# 防攻击
net.ipv4.conf.all.rp_filter = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
```

<!-- TODO: 补充其他已生效的安全基线配置 -->

---

## 监控与审计

| 工具 | 用途 | 配置状态 |
|------|------|----------|
| auditd | 系统调用审计 | <!-- TODO: 补充 --> |
| rkhunter | Rootkit 检测 | <!-- TODO: 补充 --> |
| lynis | 安全审计扫描 | <!-- TODO: 补充 --> |
| netstat/ss | 网络连接监控 | <!-- TODO: 补充 --> |

---

## 相关页面

- [[deployment/network-security]] — 网络安全详情（防火墙规则细化、CTP 专线）
- [[deployment/environment]] — Python 运行环境与 vnpy 安装
- [[deployment/process-management]] — systemd/supervisor 进程守护
- [[monitoring/alerting]] — 安全事件告警配置
- [[troubleshooting/connection-issues]] — CTP 连接问题排查
