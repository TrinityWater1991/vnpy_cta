---
title: 交易数据管理
category: data-management
tags:
  - 交易数据
  - 订单
  - 成交
  - 持仓
  - 资金
  - 数据库
created: 2026-07-16
updated: 2026-07-16
---

# 交易数据管理

## 一、数据类型总览

| 数据类型 | 数据来源 | 实时/历史 | 存储目标 | 关联文档 |
|---------|---------|-----------|---------|---------|
| 委托记录 | CTP / 交易接口 | 实时 + 历史 | TODO 数据库 | [[market-data]] |
| 成交记录 | CTP / 交易接口 | 实时 + 历史 | TODO 数据库 | [[market-data]] |
| 持仓数据 | CTP / 结算报表 | 日终 | TODO 数据库 | — |
| 资金/账户数据 | CTP / 结算报表 | 日终 | TODO 数据库 | — |

## 二、数据表结构

### 2.1 委托记录表 (`d_order` / `order`)

| 字段名 | 类型 | 说明 | 是否必填 | 备注 |
|-------|------|------|---------|------|
| orderid | TODO | 委托编号 | 是 | TODO |
| vt_orderid | TODO | 虚拟委托编号 | 是 | TODO |
| symbol | TODO | 合约代码 | 是 | — |
| exchange | TODO | 交易所 | 是 | — |
| direction | TODO | 买卖方向 | 是 | TODO |
| offset | TODO | 开平标志 | 是 | TODO |
| price | TODO | 委托价格 | 是 | — |
| volume | TODO | 委托数量 | 是 | — |
| traded | TODO | 成交数量 | 是 | — |
| status | TODO | 委托状态 | 是 | TODO |
| datetime | TODO | 委托时间 | 是 | — |
| gateway_name | TODO | 接口名称 | 是 | — |

### 2.2 成交记录表 (`d_trade` / `trade`)

| 字段名 | 类型 | 说明 | 是否必填 | 备注 |
|-------|------|------|---------|------|
| tradeid | TODO | 成交编号 | 是 | TODO |
| vt_tradeid | TODO | 虚拟成交编号 | 是 | TODO |
| orderid | TODO | 对应委托编号 | 是 | — |
| symbol | TODO | 合约代码 | 是 | — |
| direction | TODO | 买卖方向 | 是 | — |
| offset | TODO | 开平标志 | 是 | — |
| price | TODO | 成交价格 | 是 | — |
| volume | TODO | 成交数量 | 是 | — |
| datetime | TODO | 成交时间 | 是 | — |
| commission | TODO | 手续费 | 否 | TODO |

### 2.3 持仓记录表 (`d_position` / `position`)

| 字段名 | 类型 | 说明 | 是否必填 | 备注 |
|-------|------|------|---------|------|
| symbol | TODO | 合约代码 | 是 | — |
| exchange | TODO | 交易所 | 是 | — |
| direction | TODO | 持仓方向 | 是 | 净/多/空 |
| volume | TODO | 持仓数量 | 是 | — |
| frozen | TODO | 冻结数量 | 是 | — |
| price | TODO | 持仓均价 | 是 | — |
| pnl | TODO | 持仓盈亏 | 是 | — |
| yd_volume | TODO | 昨仓数量 | 是 | — |
| datetime | TODO | 更新时间 | 是 | — |

### 2.4 资金/账户数据表 (`d_account` / `account`)

| 字段名 | 类型 | 说明 | 是否必填 | 备注 |
|-------|------|------|---------|------|
| accountid | TODO | 账户编号 | 是 | — |
| balance | TODO | 静态权益 | 是 | — |
| frozen | TODO | 冻结资金 | 是 | — |
| available | TODO | 可用资金 | 是 | — |
| pnl | TODO | 盈亏 | 是 | — |
| margin | TODO | 占用保证金 | 是 | — |
| commission | TODO | 手续费 | 是 | — |
| datetime | TODO | 更新时间 | 是 | — |

## 三、常用查询

### 3.1 当日委托查询

```sql
-- TODO: 补全数据库类型和表名
SELECT * FROM d_order
WHERE datetime >= CURRENT_DATE
ORDER BY datetime DESC;
```

### 3.2 持仓汇总查询

```sql
-- TODO: 按合约汇总持仓
SELECT symbol, direction, SUM(volume) AS total_volume
FROM d_position
GROUP BY symbol, direction;
```

### 3.3 成交与委托关联查询

```sql
-- TODO: 关联委托与成交表
SELECT o.orderid, o.symbol, t.tradeid, t.price, t.volume
FROM d_order o
LEFT JOIN d_trade t ON o.orderid = t.orderid
WHERE o.datetime >= CURRENT_DATE;
```

### 3.4 TODO

- TODO: 历史盈亏统计查询
- TODO: 手续费汇总查询
- TODO: 特定策略交易流水查询

## 四、数据导出

### 4.1 导出格式

| 数据类型 | 导出格式 | 导出频率 | 导出目标 |
|---------|---------|---------|---------|
| 委托记录 | CSV / TODO | 日终 / 按需 | TODO |
| 成交记录 | CSV / TODO | 日终 / 按需 | TODO |
| 持仓快照 | CSV / TODO | 日终 | TODO |
| 资金流水 | CSV / TODO | 日终 | TODO |

### 4.2 导出流程

- TODO: 数据导出手动/自动触发流程
- TODO: 导出文件命名规范（如 `trades_YYYYMMDD.csv`）
- TODO: 导出数据一致性校验（行数核对、checksum）
- TODO: 导出文件加密与传输安全

### 4.3 导出工具

- TODO: 导出脚本路径与使用方法
- TODO: 导出的数据归档参见 [[backup]]

## 五、TODO

- TODO: 数据库备份策略参见 [[backup]]
- TODO: 历史数据保留策略参见 [[retention]]
- TODO: 交易数据异常核对与修复流程
- TODO: 多数据源（SimNow / 生产环境）切换时的数据兼容性检查
