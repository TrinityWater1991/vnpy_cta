---
title: "数据库配置"
category: "deployment"
tags: [database, mongodb, mysql, sqlite, influxdb, configuration]
created: 2026-07-16
updated: 2026-07-16
---

# 数据库配置

> 本文档说明 vnpy CTA 实盘系统的数据库选型、配置与优化。当前生产环境默认使用 SQLite 作为主力数据库，同时提供 MongoDB/MySQL 作为备选方案。

---

## 选型决策

### 数据库对比

| 特性 | SQLite | MongoDB | MySQL / PostgreSQL |
|------|--------|---------|-------------------|
| 部署复杂度 | 无需独立服务进程 | 需要部署 MongoDB 服务 | 需要部署 RDBMS 服务 |
| 性能（K 线场景） | 单机足够 | 高并发较好 | 中等 |
| 数据容量 | GB 级别 | TB 级别 | TB 级别 |
| 备份恢复 | 拷贝文件即可 | mongodump | mysqldump / pg_dump |
| 集群支持 | 不支持 | 支持副本集/分片 | 支持主从/集群 |
| 适合场景 | 单机实盘、开发测试 | 多实例、大规模数据 | 已有运维体系、合规要求 |

### 当前决策

| 环境 | 数据库 | 原因 |
|------|--------|------|
| 生产（主） | SQLite | 部署简单，单机实盘数据量可控，无需额外服务 |
| 生产（备选） | MongoDB | 高可用要求时启用，支持副本集 |
| 回测 / 分析 | SQLite / MongoDB | 回测数据量大时建议 MongoDB |

<!-- TODO: 确认当前实际生产环境使用的数据库类型和版本 -->

---

## SQLite 配置

### vnpy 配置 (`vt_setting.json`)

```json
{
    "database.name": "sqlite",
    "database.database": "database.db",
    "database.host": "",
    "database.port": 0,
    "database.user": "",
    "database.password": "",
    "database.timezone": "Asia/Shanghai"
}
```

### 数据库文件位置

```bash
# 默认路径（项目根目录下的 database.db）
/opt/vnpy/instance/database.db

# 查看文件大小
$ ls -lh /opt/vnpy/instance/database.db

# 备份数据库
$ cp /opt/vnpy/instance/database.db /backup/database-$(date +%Y%m%d).db
```

### 维护命令

```bash
# SQLite 手动 VACUUM（回收空间）
$ sqlite3 /opt/vnpy/instance/database.db "VACUUM;"

# 查看表结构
$ sqlite3 /opt/vnpy/instance/database.db ".tables"

# 数据量统计
$ sqlite3 /opt/vnpy/instance/database.db "
    SELECT name, COUNT(*) as rows
    FROM sqlite_master
    JOIN (SELECT name FROM sqlite_master WHERE type='table')
    GROUP BY name;
"
```

<!-- TODO: 确认 SQLite 数据库文件实际路径 -->
<!-- TODO: 补充数据库文件大小监控阈值 -->

---

## MongoDB 配置（备选方案）

### 安装

```bash
# 导入 MongoDB GPG 密钥
$ wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -

# 添加源并安装
$ echo "deb [ arch=amd64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
$ sudo apt update && sudo apt install -y mongodb-org
```

### vnpy 配置

```json
{
    "database.name": "mongodb",
    "database.database": "vnpy",
    "database.host": "127.0.0.1",
    "database.port": 27017,
    "database.user": "vnpy_user",
    "database.password": "<password>",
    "database.timezone": "Asia/Shanghai"
}
```

### 索引优化

```javascript
// MongoDB Shell 中创建索引
use vnpy;

// K 线数据索引
db.daily_bar.createIndex({symbol: 1, interval: 1, datetime: -1});
db.hour_bar.createIndex({symbol: 1, interval: 1, datetime: -1});
db.minute_bar.createIndex({symbol: 1, interval: 1, datetime: -1});

// tick 数据索引
db.tick_data.createIndex({symbol: 1, datetime: -1});

// 交易记录索引
db.trade_data.createIndex({orderid: 1});
db.order_data.createIndex({orderid: 1});
```

<!-- TODO: 确认是否实际使用 MongoDB，补充连接字符串和认证信息 -->

---

## MySQL 配置（备选方案）

### vnpy 配置

```json
{
    "database.name": "mysql",
    "database.database": "vnpy",
    "database.host": "127.0.0.1",
    "database.port": 3306,
    "database.user": "vnpy_user",
    "database.password": "<password>",
    "database.timezone": "Asia/Shanghai"
}
```

<!-- TODO: 补充 MySQL 建表脚本（如使用） -->
<!-- TODO: 补充连接池配置与性能调优参数 -->

---

## 数据库运维

### 备份策略

| 数据库类型 | 备份方式 | 频率 | 保留周期 |
|------------|----------|------|----------|
| SQLite | 文件拷贝 | 每日 | 30 天 |
| MongoDB | mongodump | 每日 | 30 天 |
| MySQL | mysqldump | 每日 | 30 天 |

<!-- TODO: 补充备份脚本路径和 cron 配置 -->

### 监控指标

| 指标 | SQLite | MongoDB | MySQL |
|------|--------|---------|-------|
| 数据文件大小 | `ls -lh database.db` | `db.stats().dataSize` | `SELECT table_schema ...` |
| 连接数 | 单进程 | `serverStatus().connections` | `SHOW PROCESSLIST` |
| 查询延迟 | I/O 决定 | `db.currentOp()` | `SHOW FULL PROCESSLIST` |
| 磁盘使用率 | `df -h` | `df -h` | `df -h` |

<!-- TODO: 补充数据库监控告警阈值配置 -->

---

## 相关页面

- [[deployment/environment]] — Python 环境与依赖安装
- [[deployment/backup]] — 备份策略与恢复演练
- [[data-management/market-data]] — 行情数据源接入与存储
- [[data-management/trade-data]] — 交易数据存储与查询
- [[monitoring/metrics]] — 数据库监控指标定义
