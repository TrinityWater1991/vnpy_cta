# vnpy_cta

基于 [VeighNa (vnpy)](https://github.com/vnpy/vnpy) 的 CTA 实盘交易系统。

## 结构

```
vnpy_cta/
├── run_headless.py              # 无界面实盘入口
├── strategies/                  # CTA 策略
├── configs/                     # 实盘配置（CTP 连接 + 策略参数）
├── scripts/                     # 运维脚本
├── logs/                        # 运行时日志
└── requirements_freezed.txt     # 完整依赖清单
```

## 部署

1. `./scripts/deploy_setup.sh`  初始化环境
2. 编辑 `configs/vt_setting.json` 填入 CTP 账户
3. `./scripts/start.sh`  启动交易系统
