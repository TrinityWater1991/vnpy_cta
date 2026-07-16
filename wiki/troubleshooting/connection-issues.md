---
title: "CTP 连接问题排查"
category: "troubleshooting"
tags: [ctp, connection, network, troubleshooting]
created: 2026-07-16
updated: 2026-07-16
---

# CTP 连接问题排查

> 本页记录 CTP 行情和交易网关的连接异常排查方法。

## 常见连接错误码

<!-- TODO: CTP 常见错误码及含义 -->

| 错误码 | 含义 | 常见原因 | 解决方案 |
|--------|------|----------|----------|
| （待补充） | | | |

## 行情连接异常

### 现象：行情中断

**排查步骤**：

1. 检查网络连通性：`ping <CTP 行情前置机 IP>`
2. 检查防火墙是否放行行情端口
3. 检查 CTP 账号是否过期
4. 查看行情网关日志

### 现象：行情延迟

**排查步骤**：

1. 检测网络延迟：`ping` 持续监控
2. 对比其他行情源
3. 检查系统负载（CPU/内存）

## 交易连接异常

### 现象：登录失败

**排查步骤**：

1. 检查 BrokerID / UserID / Password 是否正确
2. 检查 CTP 账号是否被锁定
3. 检查交易时段（非交易时段无法登录）
4. 检查 IP/MAC 白名单是否配置

### 现象：盘中断连

**排查步骤**：

1. 检查网络是否中断
2. 检查 CTP 服务器是否在维护
3. 检查本地防火墙/VPN 状态

## 网络诊断命令

```bash
# 测试连通性
ping <CTP 前置机 IP>
telnet <CTP 前置机 IP> <端口>
nc -zv <CTP 前置机 IP> <端口>

# 查看网络连接状态
ss -tuln | grep <端口>
```

## 相关页面

- [[common-issues]] — 常见问题汇总
- [[diagnostic-tools]] — 诊断工具
- [[../deployment/network-security]] — 网络配置
- [[../reference/ctp-specs]] — CTP 接口说明
