"""qwatch v0.4 三策略模拟器：2 个账户（国金证券 / 徽商期货）+ 3 个策略 + 4 个稳定进程。

先启动 v0.4 后端：
    python -m backend
再运行模拟器（Ctrl+C 退出）：
    python -m sim.run

环境变量：
    QWATCH_URL           后端地址，默认 http://127.0.0.1:8080
    QWATCH_PASSWORD      登录密码，默认 qwatch
    QWATCH_SIM_LOG_DIR   SDK 日志目录，默认仓库根 logs/（自测时可指向临时目录）

每个策略一个 token，缓存复用 data/sim_tokens.json；进程名固定（rb / IF / ag / au），
白银波段是双进程策略。进程只上报心跳 / tick / msg / signal / 所属账户权益，无 PnL。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = ROOT / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from qwatch import Qwatch  # noqa: E402

DEFAULT_URL = "http://127.0.0.1:8080"
DEFAULT_PASSWORD = "qwatch"
TOKENS_PATH = ROOT / "data" / "sim_tokens.json"
LOG_DIR = Path(os.environ.get("QWATCH_SIM_LOG_DIR", str(ROOT / "logs")))
HEARTBEAT_S = 30
TICK_S = 10
REQUEST_TIMEOUT_S = 10

# 2 个账户：股票账户 + 期货账户（名称/券商来自 v0.4 契约示例）
ACCOUNTS: list[dict[str, Any]] = [
    {"name": "国金证券", "broker": "国金证券", "description": "股票账户，模拟黑色系与贵金属持仓"},
    {"name": "徽商期货", "broker": "徽商期货", "description": "期货账户，模拟股指日内交易"},
]

# 3 个策略按账户分配；instruments 是稳定进程名，换月只换合约代码、不改进程名。
STRATEGIES: list[dict[str, Any]] = [
    {
        "name": "螺纹钢趋势",
        "account": "国金证券",
        "description": "黑色系 15 分钟级别趋势跟踪，夜盘连续持有。",
        "processes": [
            {
                "instrument": "rb", "contract": "rb2601", "base_price": 3510.0,
                "qty_range": (2, 8), "signal_seconds": (30, 45), "long_bias": 0.7,
                "signals": ["均线金叉", "突破前高", "回踩确认", "趋势止盈", "ATR 止损"],
                "messages": ["夜盘正常", "行情震荡", "等待突破"],
            },
        ],
    },
    {
        "name": "股指日内",
        "account": "徽商期货",
        "description": "IF 日内动量，开盘后半小时入场，收盘前平仓。",
        "processes": [
            {
                "instrument": "IF", "contract": "IF2612", "base_price": 3985.0,
                "qty_range": (1, 3), "signal_seconds": (15, 25), "long_bias": 0.55,
                "signals": ["开盘动能", "日内新高", "动量衰减", "止损离场", "收盘前平仓"],
                "messages": ["盘中监控", "波动放大", "等待收盘"],
            },
        ],
    },
    {
        "name": "白银波段",
        "account": "国金证券",
        "description": "贵金属波段，ATR 止损，隔夜仓位不超过 30%（ag / au 双进程）。",
        "processes": [
            {
                "instrument": "ag", "contract": "ag2601", "base_price": 7700.0,
                "qty_range": (1, 5), "signal_seconds": (20, 40), "long_bias": 0.5,
                "signals": ["贵金属走强", "波段减仓", "止盈离场", "ATR 止损"],
                "messages": ["夜盘回补", "金银比修复"],
            },
            {
                "instrument": "au", "contract": "au2601", "base_price": 625.0,
                "qty_range": (1, 3), "signal_seconds": (25, 45), "long_bias": 0.5,
                "signals": ["金价新高", "波段止盈", "避险升温"],
                "messages": ["贵金属监控"],
            },
        ],
    },
]

ACCOUNT_BASE_EQUITY = {"国金证券": 2_000_000.0, "徽商期货": 1_200_000.0}


# ---------- HTTP ----------

def _request(
    url: str, method: str, path: str, payload: dict[str, Any] | None = None, token: str | None = None
) -> Any:
    """调用后端 JSON API；失败抛出带 detail 的 RuntimeError。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url.rstrip("/") + path, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
            raw = response.read()
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read() or b"{}").get("detail")
        except ValueError:
            detail = None
        raise RuntimeError(f"{method} {path} 失败：{detail or ('HTTP ' + str(exc.code))}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"{method} {path} 失败：{exc}") from None
    return json.loads(raw) if raw else {}


def login(url: str, password: str) -> str:
    """密码登录，返回后台会话 token。"""
    return str(_request(url, "POST", "/api/v1/auth/login", {"password": password})["token"])


def ensure_accounts(url: str, session: str) -> dict[str, dict[str, Any]]:
    """按名称复用或创建 2 个账户，返回 name -> account。"""
    items = _request(url, "GET", "/api/v1/accounts", token=session)["items"]
    by_name = {item["name"]: item for item in items}
    accounts: dict[str, dict[str, Any]] = {}
    for spec in ACCOUNTS:
        account = by_name.get(spec["name"])
        if account is None:
            created = _request(
                url, "POST", "/api/v1/accounts",
                {"name": spec["name"], "broker": spec["broker"], "description": spec["description"]},
                token=session,
            )
            account = created.get("account") or created
            print(f"创建账户 {spec['name']}（{spec['broker']}）")
        else:
            print(f"复用账户 {spec['name']}（{account.get('broker') or spec['broker']}）")
        accounts[spec["name"]] = account
    return accounts


def ensure_runners(url: str, session: str, accounts: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按账户分配复用或创建三个策略组，返回 name -> runner。"""
    items = _request(url, "GET", "/api/v1/runners", token=session)["items"]
    by_name = {item["name"]: item for item in items}
    runners: dict[str, dict[str, Any]] = {}
    for spec in STRATEGIES:
        account = accounts[spec["account"]]
        runner = by_name.get(spec["name"])
        if runner is None:
            created = _request(
                url, "POST", "/api/v1/runners",
                {"name": spec["name"], "description": spec["description"], "account_id": account["id"]},
                token=session,
            )
            runner = created.get("runner") or created
            print(f"创建策略 {spec['name']}（账户：{spec['account']}）")
        else:
            actual = runner.get("account_name") or runner.get("account_id")
            if runner.get("account_id") and runner.get("account_id") != account["id"]:
                updated = _request(
                    url, "PATCH", "/api/v1/runners/" + runner["id"],
                    {"account_id": account["id"]}, token=session,
                )
                runner = updated.get("runner") or runner
                print(f"迁移策略 {spec['name']} 到账户 {spec['account']}")
            else:
                print(f"复用策略 {spec['name']}（账户：{actual or spec['account']}）")
        runners[spec["name"]] = runner
    return runners


def _token_alive(url: str, token: str, instrument: str) -> bool:
    """带 instrument 发一次空心跳，探测令牌是否仍然有效（不产生“主账户”幽灵进程）。"""
    try:
        _request(
            url, "POST", "/api/v1/report",
            {"ts": datetime.now().astimezone().isoformat(timespec="milliseconds"), "instrument": instrument},
            token,
        )
    except RuntimeError:
        return False
    return True


def _load_token_cache() -> dict[str, Any]:
    try:
        data = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_token_cache(cache: dict[str, Any]) -> None:
    TOKENS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = TOKENS_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(TOKENS_PATH)


def ensure_tokens(
    url: str, session: str, runners: dict[str, dict[str, Any]], accounts: dict[str, dict[str, Any]]
) -> dict[str, str]:
    """复用 data/sim_tokens.json 中有效的令牌，缺失或失效则重新创建；返回 name -> token。"""
    cache = _load_token_cache()
    same_server = cache.get("url") == url
    cached_strategies: dict[str, Any] = (cache.get("strategies") or {}) if same_server else {}
    tokens: dict[str, str] = {}
    for spec in STRATEGIES:
        runner = runners[spec["name"]]
        cached = cached_strategies.get(spec["name"]) or {}
        token = str(cached.get("token") or "")
        account = accounts[spec["account"]]
        probe_instrument = str(spec["processes"][0]["instrument"])
        if token and cached.get("runner_id") == runner["id"] and _token_alive(url, token, probe_instrument):
            tokens[spec["name"]] = token
            cached_strategies[spec["name"]] = {
                "runner_id": runner["id"], "token": token, "account_id": account["id"],
            }
            print(f"复用令牌 {spec['name']}（{token[:7]}…{token[-4:]}）")
            continue
        created = _request(
            url, "POST", "/api/v1/tokens",
            {"name": spec["name"] + " · 模拟器", "runner_id": runner["id"]},
            token=session,
        )
        token = str(created.get("token") or (created.get("record") or {}).get("token") or "")
        if not token:
            raise RuntimeError("创建令牌失败：响应缺少 token 字段")
        tokens[spec["name"]] = token
        cached_strategies[spec["name"]] = {
            "runner_id": runner["id"], "token": token, "account_id": account["id"],
        }
        prefix = (created.get("record") or {}).get("token_prefix") or (token[:7] + "…" + token[-4:])
        print(f"创建令牌 {spec['name']}（{prefix}）")

    _save_token_cache({
        "url": url,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "accounts": {spec["name"]: accounts[spec["name"]]["id"] for spec in ACCOUNTS},
        "strategies": cached_strategies,
    })
    print(f"令牌已保存到 {TOKENS_PATH}")
    return tokens


# ---------- 模拟进程 ----------

class AccountLedger:
    """账户级权益账本：同账户下多个进程共享，最后一次上报为准。"""

    def __init__(self, name: str, base_equity: float) -> None:
        self.name = name
        self.base_equity = float(base_equity)
        self._value = self.base_equity
        self._lock = threading.Lock()
        self._rng = random.Random("ledger-" + name)

    @property
    def value(self) -> float:
        with self._lock:
            return round(self._value, 2)

    def step(self) -> float:
        with self._lock:
            self._value = max(1.0, self._value * (1 + self._rng.gauss(0.0002, 0.0008)))
            return round(self._value, 2)


def _emit_signal(
    q: Qwatch,
    label: str,
    process: dict[str, Any],
    position: tuple[str, int] | None,
    rnd: random.Random,
) -> tuple[str, int] | None:
    """按当前持仓状态生成一个信号（只调 signal，不发 PnL），返回更新后的持仓。"""
    contract = process["contract"]
    price = round(process["base_price"] * (1 + rnd.uniform(-0.012, 0.012)), 2)
    if position is None:
        direction = "long" if rnd.random() < process["long_bias"] else "short"
        action = "open"
        qty = rnd.randint(*process["qty_range"])
    else:
        direction, held = position
        roll = rnd.random()
        if roll < 0.4:
            action, qty = "close", held
        elif roll < 0.7:
            action, qty = "add", rnd.randint(*process["qty_range"])
        else:
            action, qty = "reduce", max(1, held // 2)

    q.signal(contract, direction, action, qty, price=price, msg=rnd.choice(process["signals"]))
    print(f"[{label}] 信号 {contract} {direction}/{action} {qty} @ {price}")

    if action == "open":
        return direction, qty
    if action == "add":
        return direction, position[1] + qty
    if action == "reduce":
        remaining = position[1] - qty
        return None if remaining <= 0 else (direction, remaining)
    return None


def _run_process(
    strategy: dict[str, Any], process: dict[str, Any], url: str, token: str,
    ledger: AccountLedger, stop: threading.Event,
) -> None:
    """一个进程一个 Qwatch：tick/msg/signal/equity 全部非阻塞入队，后台 worker 负责发送。"""
    label = strategy["name"] + "/" + process["instrument"]
    rnd = random.Random(f"{label}-{time.time_ns()}")
    q = Qwatch(
        url, token, heartbeat=HEARTBEAT_S, instrument=process["instrument"], log_dir=str(LOG_DIR),
    )
    loops = signal_count = msg_count = equity_count = 0
    position: tuple[str, int] | None = None
    next_signal = time.monotonic() + rnd.uniform(*process["signal_seconds"])
    next_msg = time.monotonic() + rnd.uniform(20, 40)
    next_equity = time.monotonic() + rnd.uniform(10, 20)
    try:
        while not stop.is_set():
            loops += 1
            q.tick()
            now = time.monotonic()
            if now >= next_signal:
                position = _emit_signal(q, label, process, position, rnd)
                signal_count += 1
                next_signal = now + rnd.uniform(*process["signal_seconds"])
            if now >= next_msg:
                text = rnd.choice(process["messages"])
                q.msg(text)
                msg_count += 1
                print(f"[{label}] 动态 {text}")
                next_msg = now + rnd.uniform(30, 60)
            if now >= next_equity:
                value = ledger.step()
                q.equity(value)
                equity_count += 1
                print(f"[{label}] 账户权益 {ledger.name} {value:,.2f}")
                next_equity = now + rnd.uniform(20, 40)
            stop.wait(TICK_S)
    finally:
        q.close()
        stats = q.stats
        print(
            f"[{label}] 已停止：loop={loops} 信号={signal_count} 动态={msg_count} 权益={equity_count} "
            f"上报={stats['sent']} 失败={stats['failed']} 重试={stats['retried']} 丢弃={stats['dropped']}"
        )


# ---------- 入口 ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="qwatch v0.4 双账户三策略模拟器")
    parser.add_argument("--duration", type=float, default=0.0, help="运行秒数，0 表示一直运行到 Ctrl+C（便于自测）")
    args = parser.parse_args()

    url = os.environ.get("QWATCH_URL", DEFAULT_URL).rstrip("/")
    password = os.environ.get("QWATCH_PASSWORD", DEFAULT_PASSWORD)
    print(f"连接后端 {url}")
    try:
        session = login(url, password)
        accounts = ensure_accounts(url, session)
        runners = ensure_runners(url, session, accounts)
        tokens = ensure_tokens(url, session, runners, accounts)
    except RuntimeError as exc:
        print(f"启动失败：{exc}")
        return 1

    ledgers = {spec["name"]: AccountLedger(spec["name"], ACCOUNT_BASE_EQUITY[spec["name"]]) for spec in ACCOUNTS}
    strategy_account = {spec["name"]: spec["account"] for spec in STRATEGIES}
    stop = threading.Event()
    tasks = [
        (spec, process)
        for spec in STRATEGIES
        for process in spec["processes"]
    ]
    threads = [
        threading.Thread(
            target=_run_process,
            args=(spec, process, url, tokens[spec["name"]], ledgers[strategy_account[spec["name"]]], stop),
            name=f"sim-{spec['name']}-{process['instrument']}", daemon=True,
        )
        for spec, process in tasks
    ]
    try:
        for thread in threads:
            thread.start()
        print(
            f"模拟已启动：{len(ACCOUNTS)} 个账户 / {len(STRATEGIES)} 个策略 / {len(tasks)} 个进程"
            f"（心跳 {HEARTBEAT_S}s，tick {TICK_S}s）；Ctrl+C 退出。"
        )
        for account in ACCOUNTS:
            names = [spec["name"] for spec in STRATEGIES if spec["account"] == account["name"]]
            print(f"  账户 {account['name']}：{'、'.join(names)}")
        if args.duration > 0:
            stop.wait(args.duration)
            print(f"运行满 {args.duration:.0f}s，开始退出 ...")
        else:
            while not stop.wait(0.5):
                pass
    except KeyboardInterrupt:
        print("\n收到 Ctrl+C，开始退出 ...")
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=15)

    print("模拟已退出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
