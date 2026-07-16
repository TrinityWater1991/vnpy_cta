---
title: 外部资源索引
category: reference
tags:
  - links
  - resources
  - community
created: 2026-07-16
updated: 2026-07-16
---

# 外部资源索引

> 社区、工具、数据源等外部资源汇总。

---

## 官方资源

| 资源 | 链接 | 说明 |
|------|------|------|
| vnpy 官网 | [https://www.vnpy.com](https://www.vnpy.com) | 官方发布、文档入口 |
| GitHub 仓库 | [https://github.com/vnpy/vnpy](https://github.com/vnpy/vnpy) | 源码、Issue、Release |
| GitHub Issues | [https://github.com/vnpy/vnpy/issues](https://github.com/vnpy/vnpy/issues) | Bug 跟踪、功能请求 |
| GitHub Releases | [https://github.com/vnpy/vnpy/releases](https://github.com/vnpy/vnpy/releases) | 版本发布说明 |
| 官方文档站 | [https://www.vnpy.com/docs](https://www.vnpy.com/docs) | 完整文档（中文） |
| 策略示例 | [https://github.com/vnpy/vnpy/tree/master/examples](https://github.com/vnpy/vnpy/tree/master/examples) | 官方示例策略 |

> 内部文档索引参见 [[vnpy-docs]]。

---

## 社区

| 资源 | 地址 | 说明 |
|------|------|------|
| 官方论坛 | [https://www.vnpy.com/forum](https://www.vnpy.com/forum) | 问答、经验分享 |
| 微信公众号 | `vnpy-community` | 公告、技术文章 |
| QQ 群 | TODO | 日常交流 |
| 知识星球 | TODO | 深度内容 |
| CSDN 专栏 | TODO | 技术博客聚合 |

---

## 工具

### 本地工具

| 工具 | 用途 | 相关配置 |
|------|------|----------|
| Obsidian | Wiki 编辑 | 本地 Markdown 知识库 |
| Grafana | 监控面板 | 参见 [[commands#TODO|监控命令]] |
| PostgreSQL Client | 数据查询 | 参见 [[commands#数据库操作]] |
| Systemd Journal | 日志查看 | 参见 [[commands#日志查看]] |
| VSCode | 代码开发 | `/home/admin/Desktop/vnpy_cta` |

### 命令行工具

```bash
# 磁盘分析
ncdu /path/to/data/

# 网络诊断
mtr <ctp_server_ip>

# 性能分析
htop
iotop
```

## 学习资源

| 资源 | 链接 | 说明 |
|------|------|------|
| Python 量化教程 | [https://www.vnpy.com/docs/cn/quant.html](https://www.vnpy.com/docs/cn/quant.html) | vnpy 官方入门 |
| CTP API 文档 | [http://www.sfit.com.cn/](http://www.sfit.com.cn/) | 上期技术 CTP 文档 |
| 期货交易所规则 | TODO | 各交易所官网 |
| 回测方法论 | TODO | 参见回测引擎相关文档 |
| CTA 策略设计 | TODO | 常见策略模式 |

### 推荐书籍

- 《Python 量化投资》 — TODO
- 《C++ 期货交易系统》 — TODO
- 《Market Microstructure》 — TODO

## 数据供应商

| 供应商 | 说明 | 备注 |
|--------|------|------|
| 天勤 (TQ) | 期货数据 | TODO |
| 聚宽 (JoinQuant) | 行情数据 | TODO |
| 米筐 (RiceQuant) | 历史数据 | TODO |
| 万得 (Wind) | 基本面数据 | TODO |
| 通联数据 (DataYes) | 综合数据 | TODO |
| CTP 直连 | 实时行情 | 参见 [[ctp-specs]] |

---

## 告警与通知

| 服务 | 用途 | 配置 |
|------|------|------|
| Grafana Alert | 策略级别告警 | TODO |
| Prometheus | 服务器监控 | TODO |
| 飞书/钉钉 Webhook | 即时通知 | TODO |
| SMS 告警 | 应急短信通知 | TODO |

---

## TODO

- [ ] 补充实际 QQ 群号
- [ ] 补充知识星球入口
- [ ] 补充 Grafana Dashboard URL
- [ ] 补充各数据供应商 API 文档链接
- [ ] 补充监控报警 Webhook 地址
- [ ] 补充应急联系电话
