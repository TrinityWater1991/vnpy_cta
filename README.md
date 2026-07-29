# vnpy_cta

基于 [VeighNa (vnpy)](https://github.com/vnpy/vnpy) 的 CTA 实盘交易系统。

项目结构遵循官方 [examples/no_ui/run.py](https://github.com/vnpy/vnpy/blob/master/examples/no_ui/run.py) 模式。

## 结构

```
vnpy_cta/
├── run.py                 # 无界面实盘入口（基于官方 no_ui/run.py）
├── vnpy_bitget/           # Bitget 交易所网关
├── strategies/            # CTA 策略
├── configs/               # 实盘配置（网关 + 策略参数）
├── scripts/               # 运维脚本
├── wiki/                  # 运维知识库
├── vnpy/                  # 官方 vnpy 源码
├── logs/                  # 运行时日志（gitignored）
└── .vntrader/             # vnpy 运行时数据（gitignored）
```

## 部署

1. `./scripts/deploy_setup.sh`  初始化环境
2. 编辑 `configs/vt_setting.json` 填入 Bitget API Key/Secret/Passphrase
3. `./scripts/start.sh`  启动交易系统

## 官方源码

```bash
./scripts/setup_official_repos.sh  # 克隆 vnpy/vnpy_ctastrategy/vnpy_datamanager 到 _official/
```
