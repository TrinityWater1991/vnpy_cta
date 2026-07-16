---
title: 事故报告模板
category: incidents
tags:
  - template
  - incident
  - sre
created: 2026-07-16
updated: 2026-07-16
---

# 事故报告模板

> 每次生产事故处理后，使用此模板记录事故详情，归档至 `wiki/incidents/` 目录。

---

## 基本信息

| 字段 | 内容 |
|------|------|
| 事故编号 | `INC-YYYY-MM-NNN` |
| 发现时间 | TODO |
| 恢复时间 | TODO |
| 持续时间 | TODO |
| 严重级别 | `P0` / `P1` / `P2` / `P3` |
| 报告人 | TODO |
| 关联策略 | [[vnpy-docs|CTA策略列表]] |

## 事故摘要

<!-- 一句话描述事故现象及影响 -->

TODO

## 时间线

| 时间 (UTC+8) | 事件 | 操作人 |
|-------------|------|--------|
| TODO | TODO | TODO |
| TODO | TODO | TODO |
| TODO | TODO | TODO |

## 影响范围

- **影响策略**：TODO（参见 [[commands#日志查看|日志查看方法]] 确认受影响策略）
- **影响账户**：TODO
- **资金损失**：TODO（如有）
- **影响时长**：TODO

## 根因分析 (5-Why)

| Why | 回答 |
|-----|------|
| 1. 发生了什么？ | TODO |
| 2. 为什么发生？ | TODO |
| 3. 为什么没被提前发现？ | TODO |
| 4. 为什么监控没有告警？ | TODO |
| 5. 根因是什么？ | TODO |

> 参见 [[ctp-specs|CTP API 规格]] 了解可能涉及的 CTP 相关根因。

## 应急响应

<!-- 描述了如何止损、切换、回滚 -->

1. TODO
2. TODO
3. TODO

相关命令参考 [[commands]]。

## 长期修复

| 操作项 | 负责人 | 截止日期 | 状态 |
|--------|--------|----------|------|
| TODO | TODO | TODO | `待办` / `进行中` / `已完成` |
| TODO | TODO | TODO | `待办` / `进行中` / `已完成` |
| TODO | TODO | TODO | `待办` / `进行中` / `已完成` |

## 经验教训

1. TODO
2. TODO
3. TODO

---

**相关链接**：[[external-links]] | [[vnpy-docs]] | [[commands]]
