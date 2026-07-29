# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

vnpy_cta is a headless production deployment of [VeighNa (vnpy) 4.4.0](https://github.com/vnpy/vnpy) CTA futures trading strategies. It runs on Python 3.13 and targets a VPS at `47.237.121.19`. The vnpy framework (`vnpy`, `vnpy_ctastrategy`, etc.) is installed via pip — this repo contains only custom strategies, configuration, and ops tooling.

**Python version: 3.13 only.** Official vnpy supports 3.10–3.13, but this project is locked to 3.13. All commands, venvs, and deployments MUST use `python3.13`.

## Environment setup

```bash
# Create venv (first time)
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify
python3.13 -c "from vnpy.event import EventEngine; from vnpy_ctastrategy import CtaStrategyApp; from vnpy_bitget import BitgetLinearGateway; print('OK')"
```

## Commands

There is no build step, no linter, and no test suite.

```bash
# Production: start / stop / status
sudo systemctl start vnpy-cta
sudo systemctl stop vnpy-cta
sudo systemctl status vnpy-cta
journalctl -u vnpy-cta -f          # follow logs

# Manual run (for debugging)
python3.13 run_headless.py

# Health check
./scripts/health_check.sh

# Backup
./scripts/backup.sh
```

## Architecture

### Entry point

[`run_headless.py`](run_headless.py) is the sole entry point. It initializes a vnpy `MainEngine` with `CtaStrategyApp`, loads strategy instances from [`configs/cta_strategy_setting.json`](configs/cta_strategy_setting.json), and blocks on `time.sleep(1)` in a loop. It registers `SIGTERM`/`SIGINT` handlers that call `stop_all_strategies()` + `main_engine.close()` for graceful shutdown. **Never use SIGKILL (`kill -9`)** — the CTP gateway won't release its session, which can cause next-day login rejection ("重复登录" error).

The script imports vnpy built-in strategy classes (`DoubleMaStrategy`, `AtrRsiStrategy`, `BollChannelStrategy`, `KingKeltnerStrategy`) as side-effect registration. Without these imports, `add_strategy()` can't resolve built-in class names. Custom strategies in `strategies/` are made importable via `sys.path.insert(0, ...)`.

### Strategy layer (`strategies/`)

All 14 strategies are custom subclasses of `CtaTemplate` from `vnpy_ctastrategy`. Each follows this pattern:

```
CtaTemplate subclass
  ├── author, parameters[], variables[]   — class-level metadata
  ├── __init__: BarGenerator + ArrayManager
  ├── on_init → load_bar(N) / on_start / on_stop
  ├── on_tick → bg.update_tick            — tick → bar synthesis
  ├── on_bar / on_window_bar              — core signal logic
  └── on_order / on_trade / on_stop_order — status callbacks
```

Key conventions:
- **`parameters` list** — strings matching class attribute names. The vnpy optimizer scans these; the GUI displays them.
- **`variables` list** — strings matching class attribute names, displayed in the real-time monitor.
- **`cancel_all()` at the top of every bar callback** — cancels unfilled stop/limit orders before re-evaluating.
- **`BarGenerator(…, window=N, on_window_bar=cb, interval=Interval.HOUR)`** — synthesize higher-timeframe bars from 1-min bars.
- **`self.buy/sell/short/cover(price, volume, stop=True)`** — `stop=True` = stop order; omit for limit order.
- **`self.write_log("message")`** — write to strategy log; surfaced in GUI or log output.

Strategy files are `snake_case`, class names are `PascalCase`. The `__init__.py` is empty — strategies are never imported directly as a package; they are resolved by `CtaEngine.add_strategy()` which searches `sys.path`.

### Configuration (`configs/`)

| File | Purpose | Git |
|------|---------|-----|
| `cta_strategy_setting.json` | Array of `{class_name, strategy_name, vt_symbol, setting}` objects loaded by `run_headless.py` | tracked |
| `cta_strategy_setting.json.template` | Template for new deployments | tracked |
| `vt_setting.json` | CTP credentials (`brokerid`, `userid`, `password`, gateway addresses) | **gitignored** |
| `vt_setting.json.template` | Empty `{}` template; fill with real creds at deploy time | tracked |

### Production ops (`scripts/`)

| Script | Purpose |
|--------|---------|
| `deploy_setup.sh` | First-time VPS setup: venv, pip install, directories, systemd service |
| `start.sh` / `stop.sh` | Start/stop via systemd (fallback to nohup / kill) |
| `health_check.sh` | Process, database file, disk, memory, recent log checks |
| `backup.sh` | Backup `.vntrader/database.db` + configs; 30-day retention |
| `vnpy-cta.service` | systemd unit: restart on failure, logs to `logs/cta.log` |

## Code conventions

Strategies and scripts in this repo follow the conventions from the research project (`cta_harness/AGENTS.md`). Key rules:

**Python**
- Strict PEP-8. Google-style docstrings (opening/closing `"""` on their own lines).
- Comments explain *why*, not *what*.

**Types**
- Full type annotations on all function signatures, returns, class attributes, and non-obvious locals.
- Use explicit types (`dataclass`, `TypedDict`, `Enum`) over loose dicts. Avoid `Any`.

**Modification**
- Minimal diffs — only change what the task requires. Match existing code style even if you prefer another.
- Don't add abstractions, config options, or helper functions that aren't needed now. Simple code that works beats future-proofed complexity.
- If you spot an unrelated problem, mention it but don't touch it.

**Naming**
- Strategy files: `snake_case_strategy.py`. Strategy classes: `PascalCaseStrategy`.
- Names ≤ 3 words, use full words (no cryptic abbreviations).

**Strategy code**
- Subclass `CtaTemplate`. Must define `parameters` and `variables` class lists.
- Use `BarGenerator` for multi-timeframe bars, `ArrayManager` for indicators.
- Refer to existing strategies in `strategies/` as reference.

## Wiki layer (`wiki/`)

`wiki/` is the primary store of production ops knowledge — not documentation decoration. Deployment details, config changes, incident reports, postmortems, and operational experience should all be filed here. The LLM is responsible for keeping it current and cross-referenced.

The schema is defined in [`wiki/WIKI_SCHEMA.md`](wiki/WIKI_SCHEMA.md), following the LLM Wiki pattern.

Three core operations the LLM is expected to perform:
- **Ingest** — when the user provides new information (incident report, config change, operational experience): read source → update affected pages → update `index.md` → append `log.md`.
- **Query** — answer questions by reading `index.md` first to locate relevant pages, then drilling in.
- **Lint** — periodically check for contradictions, stale content, orphan pages, missing cross-references, information gaps.

All pages use YAML frontmatter (`title`, `category`, `tags`, `created`, `updated`) for Dataview compatibility, and `[[wikilink]]` syntax for cross-references. Content is in Chinese.

## Deployment workflow

All code follows a three-stage pipeline:

```
本地开发 → GitHub 仓库 → VPS 部署
  ①           ②            ③
```

1. **本地编排开发** — 所有代码在本项目（`vnpy_cta`）内编写、测试、验证
2. **同步到 GitHub** — 代码确认无误后 `git commit` + `git push` 到远程仓库
3. **VPS 部署** — 从 GitHub `git pull` 拉取最新代码，`systemctl restart vnpy-cta` 重启服务

禁止跳过前两步直接操作 VPS。

## Deployment context

- **Target**: Python 3.13, vnpy 4.4.0, Ubuntu VPS
- **Full dependency list**: [`requirements.txt`](requirements.txt) — based on official vnpy/vnpy_ctastrategy/vnpy_datamanager pyproject.toml (~50 resolved packages, down from 334). Install on a new VPS with `pip install -r requirements.txt`.
- **Key packages**: `vnpy`, `vnpy_ctastrategy`, `vnpy_ctabacktester`, `vnpy_datamanager`, `vnpy_rqdata`, `vnpy_sqlite`
- **Runtime directories** (gitignored): `.vntrader/` (vnpy runtime + SQLite DB), `logs/` (application logs)
- **Sensitive files** (gitignored): `configs/vt_setting.json` (CTP credentials)
