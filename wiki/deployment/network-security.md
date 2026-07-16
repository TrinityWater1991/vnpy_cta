---
title: "网络安全与访问控制"
category: "deployment"
tags: [network, firewall, ssh, ctp, security, acl]
created: 2026-07-16
updated: 2026-07-16
---

# 网络安全与访问控制

> 本文档详细说明 vnpy CTA 实盘系统的网络层面安全策略，包括防火墙规则、SSH 访问控制、CTP 网络连接要求以及 API 端口防护。

---

## 网络拓扑

```
                    ┌─────────────────────┐
                    │   Internet / CTPNet │
                    └──────┬──────────────┘
                           │
                    ┌──────▼──────────────┐
                    │    VPS 公共网卡      │
                    │    eth0 (公网 IP)    │
                    └──────┬──────────────┘
                           │
                    ┌──────▼──────────────┐
                    │      iptables / ufw │
                    │   (入站白名单策略)   │
                    └──────┬──────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
    ┌───────▼──────┐ ┌────▼─────┐ ┌──────▼──────┐
    │  SSH (2222)  │ │ CTP 行情 │ │ CTP 交易    │
    │  密钥认证     │ │ 37789/tcp│ │ 37790/tcp   │
    └───────┬──────┘ └────┬─────┘ └──────┬──────┘
            │              │              │
    ┌───────▼──────────────▼──────────────▼──────┐
    │          vnpy 交易进程 (trader)             │
    │         监听: 8080(Web), 8001(API)         │
    └─────────────────────────────────────────────┘
```

<!-- TODO: 补充实际网络拓扑图（内网互联、VPN、监控服务器等关系） -->

---

## 防火墙规则

### iptables 规则集

```bash
# 清空并设置默认策略
$ iptables -P INPUT DROP
$ iptables -P FORWARD DROP
$ iptables -P OUTPUT ACCEPT

# 允许本地回环
$ iptables -A INPUT -i lo -j ACCEPT

# 允许已建立连接
$ iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# SSH 访问（指定管理 IP）
$ iptables -A INPUT -p tcp --dport 2222 -s <管理网络 CIDR> -j ACCEPT

# CTP 行情与交易端口
$ iptables -A INPUT -p tcp --dport 37789 -s <CTP 前置机 IP> -j ACCEPT
$ iptables -A INPUT -p tcp --dport 37790 -s <CTP 前置机 IP> -j ACCEPT

# vnpy Web 管理界面（内网或 VPN 专用）
$ iptables -A INPUT -p tcp --dport 8080 -s <内网 CIDR> -j ACCEPT

# REST API 端口（如启用）
$ iptables -A INPUT -p tcp --dport 8001 -s 127.0.0.1 -j ACCEPT

# ICMP Ping（可选）
$ iptables -A INPUT -p icmp --icmp-type echo-request -m limit --limit 10/minute -j ACCEPT
$ iptables -A INPUT -p icmp --icmp-type echo-request -j DROP

# 记录被拒绝的包（调试用）
$ iptables -A INPUT -j LOG --log-prefix "FW-DROP: " --log-level 4
```

<!-- TODO: 填写实际使用的 CTP 前置机 IP 地址列表 -->
<!-- TODO: 填写管理网段 CIDR -->

### ufw 等价配置

```bash
$ ufw default deny incoming
$ ufw default allow outgoing
$ ufw allow from <管理网络 CIDR> to any port 2222 proto tcp
$ ufw allow from <CTP 前置机 IP> to any port 37789 proto tcp
$ ufw allow from <CTP 前置机 IP> to any port 37790 proto tcp
$ ufw allow from <内网 CIDR> to any port 8080 proto tcp
$ ufw enable
```

<!-- TODO: 确认实际使用 iptables 还是 ufw，补充生效中的规则导出结果 -->
<!-- TODO: 记录 `iptables-save` 或 `ufw status numbered` 的输出 -->

---

## SSH 访问控制

### 访问策略

| 策略项 | 配置 | 说明 |
|--------|------|------|
| 监听端口 | 2222 | 非默认端口，规避扫描攻击 |
| 认证方式 | 仅密钥 | 禁用密码认证 |
| 允许用户 | trader | 禁止 root 直接登录 |
| 来源 IP | 固定 IP 白名单 | 仅允许管理网络访问 |
| 登录记录 | auditd 审计 | 记录所有 SSH 登录尝试 |

### 源 IP 白名单

| 来源 | IP/CIDR | 用途 | 备注 |
|------|---------|------|------|
| 办公室网络 | <!-- TODO: 补充 --> | 运维人员日常登录 | |
| 跳板机 | <!-- TODO: 补充 --> | 堡垒机统一入口 | |
| VPN | <!-- TODO: 补充 --> | 远程应急连接 | |
| 备用线路 | <!-- TODO: 补充 --> | 主线路故障时备用 | |

---

## CTP 网络要求

### CTP 前置机连接

| 项目 | 行情前置 | 交易前置 | 说明 |
|------|----------|----------|------|
| 默认端口 | 37789 | 37790 | CTP 标准端口 |
| 协议 | TCP | TCP | 长连接，双向通讯 |
| 加密 | 无（应用层） | 无（应用层） | 需在网络层面控制 |
| 心跳间隔 | 30 秒 | 30 秒 | CTP 内部保活机制 |
| 超时阈值 | 120 秒 | 120 秒 | 超时断开重连 |

### 网络要求

| 要求 | 标准 | 说明 |
|------|------|------|
| 延迟 | < 10ms | 交易延迟要求，远超普通 Web 应用 |
| 抖动 | < 5ms | 网络抖动可能引起 CTP 断连 |
| 丢包率 | < 0.1% | 丢包率过高导致行情数据缺失 |
| 带宽 | > 5 Mbps | 行情数据峰值流量保障 |

<!-- TODO: 补充实际 CTP 前置机 IP、端口号、交易中心名称 -->
<!-- TODO: 记录 CTP 网络延迟测试结果（ping/tcping） -->

### 网络诊断命令

```bash
# TCP 连接测试
$ tcping <CTP_行情_IP> 37789
$ tcping <CTP_交易_IP> 37790

# 路由追踪
$ traceroute <CTP_前置机_IP>

# 持续 ping（丢包率检测）
$ ping -c 100 <CTP_前置机_IP>

# 带宽测试
$ iperf3 -c <测试服务器_IP>
```

---

## API 端口防护

### vnpy REST API

```json
{
    "rest_api": {
        "enable": true,
        "listen": "127.0.0.1",
        "port": 8001,
        "auth_token": "<token>",
        "tls_enable": false,
        "rate_limit": 10
    }
}
```

| 安全措施 | 说明 |
|----------|------|
| 绑定地址 | 仅监听 127.0.0.1，禁止公网直接访问 |
| 认证 Token | 启用 Token 认证，定期轮换 |
| 限速 | 限制请求频率，防止暴力破解 |
| HTTPS | 公网暴露时必须启用 TLS |
| 审计日志 | 记录所有 API 请求 |

<!-- TODO: 确认 REST API 是否启用，补充认证 Token 轮换周期 -->

---

## VPN / 隧道方案

如果需要远程安全访问，推荐以下方案：

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| WireGuard | 配置简单，性能优秀 | 需额外维护 | ⭐⭐⭐⭐⭐ |
| OpenVPN | 生态成熟，客户端多 | 配置较复杂 | ⭐⭐⭐⭐ |
| Tailscale | 零配置，基于 WireGuard | 依赖第三方服务 | ⭐⭐⭐ |
| frp 隧道 | 可穿透 NAT | 需要公网中转 | ⭐⭐ |

<!-- TODO: 确认是否需要 VPN 接入，补充实际部署方案 -->

---

## 相关页面

- [[deployment/vps-setup]] — VPS 基础安全加固（SSH、fail2ban）
- [[deployment/deploy-workflow]] — 部署流程中的网络配置步骤
- [[troubleshooting/connection-issues]] — CTP 连接异常排查
- [[monitoring/alerting]] — 网络安全事件告警配置
- [[troubleshooting/diagnostic-tools]] — 网络诊断命令汇总
