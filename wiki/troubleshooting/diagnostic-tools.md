---
title: "诊断工具与命令"
category: "troubleshooting"
tags: [diagnostic, tools, commands, debugging]
created: 2026-07-16
updated: 2026-07-16
---

# 诊断工具与命令

> 本页汇总故障排查中常用的诊断命令和工具。

## 系统诊断

### 进程检查

```bash
# 检查 vnpy 进程
ps aux | grep run_headless
systemctl status vnpy-cta

# 查看进程资源使用
top -p <PID>
htop
```

### 网络诊断

```bash
# 测试 CTP 连通性
ping <CTP 前置机 IP>
telnet <CTP 前置机 IP> <端口>
nc -zv <CTP 前置机 IP> <端口>

# 查看网络连接状态
ss -tuln
netstat -an | grep <端口>
```

### 磁盘与内存

```bash
# 磁盘使用
df -h
du -sh /path/to/data/

# 内存使用
free -h
vmstat 1
```

## 日志诊断

```bash
# 查看实时日志
tail -f logs/cta.log

# 搜索错误
grep -i "error\|exception\|traceback" logs/cta.log

# 按时间范围过滤
sed -n '/2026-07-16 09:00/,/2026-07-16 10:00/p' logs/cta.log

# systemd 日志
journalctl -u vnpy-cta -f
journalctl -u vnpy-cta --since "10 minutes ago"
```

## 数据库诊断

```bash
# SQLite 检查
sqlite3 .vntrader/database.db ".tables"
sqlite3 .vntrader/database.db "SELECT COUNT(*) FROM dbbardata;"

# 查看数据库文件大小
ls -lh .vntrader/database.db
```

## vnpy 内置诊断

<!-- TODO: vnpy 内置的调试/诊断功能 -->

## 相关页面

- [[common-issues]] — 常见问题汇总
- [[connection-issues]] — 连接问题
- [[../reference/commands]] — 常用命令速查
