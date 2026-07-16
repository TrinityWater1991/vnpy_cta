---
title: 常用命令速查表
category: reference
tags:
  - commands
  - operations
  - cheatsheet
created: 2026-07-16
updated: 2026-07-16
---

# 常用命令速查表

> 日常运维常用命令汇总。

---

## 服务管理

| 操作 | 命令 |
|------|------|
| 查看服务状态 | `systemctl status vnpy_cta` |
| 启动服务 | `systemctl start vnpy_cta` |
| 停止服务 | `systemctl stop vnpy_cta` |
| 重启服务 | `systemctl restart vnpy_cta` |
| 设置开机自启 | `systemctl enable vnpy_cta` |
| 查看服务日志 | `journalctl -u vnpy_cta -f` |
| 查看今天日志 | `journalctl -u vnpy_cta --since today` |

```bash
# 服务文件路径
/etc/systemd/system/vnpy_cta.service
```

## Git 操作

| 操作 | 命令 |
|------|------|
| 查看状态 | `git status` |
| 查看日志 | `git log --oneline -10` |
| 拉取最新代码 | `git pull` |
| 切换分支 | `git checkout <branch>` |
| 暂存更改 | `git stash` |
| 恢复暂存 | `git stash pop` |
| 查看 diff | `git diff` |
| 硬重置 | `git reset --hard HEAD` |

```bash
# 事故回滚示例
git stash                         # 暂存本地修改
git pull origin main              # 拉取最新
git reset --hard <last_stable_commit>  # 回滚到稳定版本
```

## 日志查看

| 操作 | 命令 |
|------|------|
| 实时日志 | `journalctl -u vnpy_cta -f -n 100` |
| 最近 N 条 | `journalctl -u vnpy_cta -n 200 --no-pager` |
| 时间范围 | `journalctl -u vnpy_cta --since "10 min ago"` |
| 应用日志 | `tail -f /path/to/logs/vnpy_cta.log` |
| 日志目录 | `ls -lh /var/log/vnpy_cta/` |
| 压缩轮转 | `logrotate -f /etc/logrotate.d/vnpy_cta` |
| 错误级别 | `journalctl -u vnpy_cta -p err -b` |

> 参见 [[incidents/template|事故报告模板]] 中时间线部分的日志调取方法。

## 数据库操作

| 操作 | 命令 |
|------|------|
| 连接数据库 | `psql -h <host> -U <user> -d vnpy_cta` |
| 查看表列表 | `\dt` |
| 查询持仓 | `SELECT * FROM position_data WHERE strategy='MyStrategy';` |
| 查询委托 | `SELECT * FROM order_data WHERE order_time > NOW() - INTERVAL '1 day';` |
| 查询成交 | `SELECT * FROM trade_data WHERE trade_time > NOW() - INTERVAL '1 day';` |
| 数据迁移 | TODO |
| 备份数据库 | TODO |

```sql
-- 今日委托数统计
SELECT COUNT(*) FROM order_data
WHERE order_time >= CURRENT_DATE;
```

## 文件操作

| 操作 | 命令 |
|------|------|
| 查看磁盘空间 | `df -h` |
| 查看目录大小 | `du -sh /path/to/data/` |
| 查看大文件 | `find /path/to -type f -size +100M -exec ls -lh {} \;` |
| 清理日志 | `journalctl --vacuum-time=7d` |
| 清理缓存文件 | `rm -rf /path/to/cache/*` |
| 查看文件句柄 | `lsof -p <pid> \| wc -l` |
| 数据目录概览 | `ls -lh /home/admin/Desktop/vnpy_cta/data/` |

```bash
# 磁盘告警时快速清理
sudo journalctl --vacuum-size=200M
sudo du -sh /var/log/
```

## Python / vnpy 命令

| 操作 | 命令 |
|------|------|
| 激活虚拟环境 | `source venv/bin/activate` |
| 退出虚拟环境 | `deactivate` |
| 安装依赖 | `pip install -r requirements.txt` |
| 更新依赖 | `pip install --upgrade -r requirements.txt` |
| 冻结依赖 | `pip freeze > requirements.txt` |
| 运行回测 | `python run_backtest.py --strategy MyStrategy` |
| 运行实盘 | `python run.py` |
| 启动 vnpy 终端 | `vnpy` |
| 查看策略列表 | `python run.py list_strategies` |

```bash
# 回测示例
cd /home/admin/Desktop/vnpy_cta
source venv/bin/activate
python run_backtest.py \
    --strategy GridStrategy \
    --symbol rb2205 \
    --start 20260101 \
    --end 20260630
```

## 网络与端口

| 操作 | 命令 |
|------|------|
| 查看监听端口 | `ss -tlnp` |
| 测试 CTP 连接 | `nc -zv <ip> <port>` |
| 查看连接状态 | `ss -tnp \| grep <pid>` |

> CTP 服务器地址和端口参见 [[ctp-specs|CTP API 规格]]。

---

## TODO

- [ ] 补充 Grafana 查询模板
- [ ] 补充 Redis 操作命令
- [ ] 补充数据导出命令
- [ ] 补充报警规则配置命令
