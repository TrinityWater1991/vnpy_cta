# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

vnpy_cta is a headless production deployment of [VeighNa (vnpy) 4.4.0](https://github.com/vnpy/vnpy) on Bitget U-margined futures. It runs on Python 3.13 and targets a VPS at `47.237.121.19`. The vnpy framework is installed via pip — this repo contains the Bitget gateway (`vnpy_bitget/`), custom strategies, configuration, and ops tooling.

**Python version: 3.13 only.** Official vnpy supports 3.10–3.13, but this project is locked to 3.13. All commands, venvs, and deployments MUST use `python3.13`.

## Environment setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands

```bash
# Start the trading system
source .venv/bin/activate
./scripts/proxy_tunnel.sh start   # SSH SOCKS5 → pproxy HTTP proxy chain
python3.13 run.py

# Production (systemd on VPS)
sudo systemctl start vnpy-cta / stop / status
journalctl -u vnpy-cta -f
```

## Architecture

### Entry point

[`run.py`](run.py) is the sole entry point, based on vnpy official [`examples/no_ui/run.py`](https://github.com/vnpy/vnpy/blob/master/examples/no_ui/run.py). Startup sequence:

```
① MainEngine + BitgetLinearGateway + CtaStrategyApp
② gateway.connect() → REST time sync → contracts (731) → WS channels
③ sleep(10) → sync contracts to OmsEngine → init_engine() → load strategies
④ init_all_strategies() → future.result() wait → start_all_strategies()
⑤ while True: sleep(10)
```

Key details from debugging:
- **`init_all_strategies()` returns `dict[str, Future]`** — must call `f.result()` on each future to wait for completion before `start_all_strategies()`.
- **`os.chdir(PROJECT_DIR)` before `init_engine()`** — the engine uses `Path.cwd()` to locate the `strategies/` folder.
- **Contract sync** — gateway loads 731 contracts via REST, but vnpy's event-driven registration is async. Must manually sync `gateway.symbol_contract_map` → `oms.contracts` before `init_engine()`.
- **`load_bar()` uses gateway by default** — `CtaTemplate.load_bar(N)` has `use_database=False` by default, which calls `gateway.query_history()` directly. No external datafeed needed.

### Bitget gateway (`vnpy_bitget/`)

Custom gateway for Bitget U-margined futures (API v3 UTA). Based on `vnpy_binance` architecture — 4 classes in one file:

```
BitgetLinearGateway(BaseGateway)
  ├── RestApi(RestClient)    — REST: time, contracts (v2), candles (v2)
  ├── MdApi(WebsocketClient)  — WS public: ticker, books, candle1m
  └── TradeApi(WebsocketClient) — WS private: login → place/cancel order + user data stream
```

Key implementation details:
- **API v3 UTA**: uses `/api/v3/market/time`, `/api/v3/trade/unfilled-orders`, WS `instType: "UTA"` channels. Contracts/candles still use v2 endpoints (v3 equivalents not yet stable).
- **Signing**: `Base64(HMAC-SHA256(secret, timestamp + method + path + body))`. Headers: `ACCESS-KEY`, `ACCESS-SIGN`, `ACCESS-TIMESTAMP`, `ACCESS-PASSPHRASE`.
- **`sign()` must clear `request.data = {}`** after signing, otherwise `{"signed": True}` is sent as HTTP body and Bitget returns 403.
- **Exchange enum**: `Exchange.BITGET` added to pip-installed `vnpy/trader/constant.py` + runtime fallback in `run.py`.
- **`ContractData.symbol`**: must be raw ticker (e.g. `"BTCUSDT"`). vnpy auto-generates `vt_symbol = f"{symbol}.{exchange.value}"` → `"BTCUSDT.BITGET"`. If you put `.BITGET` in `symbol`, it doubles to `"BTCUSDT.BITGET.BITGET"`.
- **Default proxy**: `127.0.0.1:1081` (pproxy HTTP proxy). See proxy chain below.
- **`productType` parameter**: Bitget v2 candles/public endpoints require `productType=USDT-FUTURES`.

### Proxy chain for Bitget access

Bitget API requires connections from the VPS IP. Local development uses a proxy chain:

```
run.py → 127.0.0.1:1081 (pproxy HTTP) → 127.0.0.1:1080 (SSH -D SOCKS5) → VPS → Bitget
```

- `./scripts/proxy_tunnel.sh start` — starts both SSH tunnel + pproxy converter
- Gateway defaults: `Proxy Host: 127.0.0.1, Proxy Port: 1081`
- On VPS deployment, proxy is unnecessary — set `Proxy Host: ""` in `vt_setting.json`

### Strategy layer (`strategies/`)

Custom subclasses of `CtaTemplate`. Conventions:
- `parameters` / `variables` class lists for optimizer and UI
- `cancel_all()` at the top of every bar callback
- `BarGenerator` + `ArrayManager` for multi-timeframe bar synthesis and indicators
- `self.buy/sell/short/cover(price, volume, stop=True)` — `stop=True` = stop order
- Files `snake_case_strategy.py`, classes `PascalCaseStrategy`

### Configuration (`configs/`)

| File | Purpose | Git |
|------|---------|-----|
| `cta_strategy_setting.json` | Strategy instances: `{class_name, strategy_name, vt_symbol, setting}` | tracked |
| `cta_strategy_setting.json.template` | Template for new deployments | tracked |
| `vt_setting.json` | Bitget API Key / Secret / Passphrase | **gitignored** |
| `vt_setting.json.template` | Template: `{"API Key": "", "API Secret": "", "API Passphrase": "", "Server": ["REAL"], "Proxy Host": "127.0.0.1", "Proxy Port": 1081}` | tracked |

### Project-local .vntrader

`run.py` overrides `cta_engine.setting_filename` and `data_filename` to point to `PROJECT_DIR/.vntrader/` instead of the global `~/.vntrader/`, isolating strategy state per project.

### Official source repos

`vnpy/`, `vnpy_ctastrategy/`, `vnpy_datamanager/` in the project root are git-cloned official source for reference. They are **gitignored** — use `pip install` for the runtime.

## Code conventions

From `cta_harness/AGENTS.md`:

**Python**: Strict PEP-8. Google-style docstrings. Comments explain *why*, not *what*.
**Types**: Full annotations on all signatures, returns, class attributes. Use `dataclass`/`TypedDict`/`Enum` over loose dicts. Avoid `Any`.
**Modification**: Minimal diffs. Match existing style. Don't add abstractions not needed now. If you spot an unrelated problem, mention it but don't touch it.
**Naming**: Strategy files `snake_case_strategy.py`, classes `PascalCaseStrategy`. ≤ 3 words, full words.

## Wiki layer (`wiki/`)

Production ops knowledge base. Schema: [`wiki/WIKI_SCHEMA.md`](wiki/WIKI_SCHEMA.md). LLM performs Ingest/Query/Lint. YAML frontmatter + `[[wikilink]]` syntax. Content in Chinese.

## Deployment workflow

```
本地开发 → GitHub 仓库 → VPS 部署
  ①           ②            ③
```

禁止跳过前两步直接操作 VPS。

## Deployment context

- **Target**: Python 3.13, vnpy 4.4.0, Alibaba Cloud Linux 3 VPS (`47.237.121.19`)
- **Dependencies**: [`requirements.txt`](requirements.txt) (~50 packages, based on official pyproject.toml)
- **Key packages**: `vnpy`, `vnpy_ctastrategy`, `vnpy_datamanager`, `vnpy_sqlite`, `vnpy_rest`, `vnpy_websocket`, `pproxy`, `PySocks`
- **Runtime dirs** (gitignored): `.vntrader/`, `logs/`
- **Sensitive** (gitignored): `configs/vt_setting.json`
