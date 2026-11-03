"""三个策略的模拟器：通过真实 HTTP API 登录 / 建策略 / 建令牌，再用 qwatch SDK 上报心跳与信号。

先启动后端并初始化基础数据（账户 / 渠道 / 日历）：
    python -m backend.seed
    python -m backend

再运行模拟器（Ctrl+C 退出）：
    python -m sim.run

环境变量：
    QWATCH_URL       后端地址，默认 http://127.0.0.1:8080
    QWATCH_PASSWORD  登录密码，默认 qwatch

令牌保存在 data/sim_tokens.json（data/ 已 gitignore）；首次运行创建，之后复用。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = ROOT / "sdk" / "python"
if str(SDK_PATH) not in sys.path:
    sys.path.insert(0, str(SDK_PATH))

from qwatch import AuthError, Qwatch  # noqa: E402

DEFAULT_URL = "http://127.0.0.1:8080"
DEFAULT_PASSWORD = "qwatch"
TOKENS_PATH = ROOT / "data" / "sim_tokens.json"
HEARTBEAT_S = 30
TICK_S = 10
REQUEST_TIMEOUT_S = 10

# 三个策略：平台 / 账户 / 品种 / 频率 / 方向偏好各不相同，尽量贴近真实交易节奏。
STRATEGIES: list[dict[str, Any]] = [
    {
        "name": "螺纹钢趋势",
        "platform": "qmt",
        "market": "CN_FUT",
        "description": "15 分钟级别黑色系趋势跟踪，夜盘连续持有。",
        "instruments": [("rb2601", 3510.0)],
        "qty_range": (2, 8),
        "signal_seconds": (30, 45),
        "long_bias": 0.7,
        "initial_equity": 348000.0,
        "messages": ["均线金叉", "突破前高", "回踩确认", "趋势止盈", "ATR 止损"],
    },
    {
        "name": "股指日内",
        "platform": "ptrade",
        "market": "CN_FUT",
        "description": "IF 日内动量，开盘后半小时入场，收盘前平仓。",
        "instruments": [("IF2612", 3985.0)],
        "qty_range": (1, 3),
        "signal_seconds": (15, 25),
        "long_bias": 0.55,
        "initial_equity": 262000.0,
        "messages": ["开盘动能", "日内新高", "动量衰减", "止损离场", "收盘前平仓"],
    },
    {
        "name": "白银波段",
        "platform": "myquant",
        "market": "CN_FUT",
        "description": "贵金属波段，ATR 止损，隔夜仓位不超过 30%。",
        "instruments": [("ag2601", 7700.0), ("au2601", 625.0)],
        "qty_range": (1, 5),
        "signal_seconds": (20, 40),
        "long_bias": 0.5,
        "initial_equity": 166000.0,
        "messages": ["贵金属走强", "波段减仓", "止盈离场", "ATR 止损", "夜盘回补"],
    },
]


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


def ensure_runners(url: str, session: str) -> dict[str, dict[str, Any]]:
    """按名字复用或创建三个策略，返回 name -> runner。"""
    items = _request(url, "GET", "/api/v1/runners", token=session)["items"]
    by_name = {item["name"]: item for item in items}
    runners: dict[str, dict[str, Any]] = {}
    for spec in STRATEGIES:
        runner = by_name.get(spec["name"])
        if runner is None:
            runner = _request(
                url, "POST", "/api/v1/runners",
                {
                    "name": spec["name"], "platform": spec["platform"], "market": spec["market"],
                    "description": spec["description"],
                },
                token=session,
            )["runner"]
            print(f"创建策略 {spec['name']}（{spec['platform']} / {spec['market']}）")
        else:
            print(f"复用策略 {spec['name']}（{runner['platform']} / {runner['market']}）")
        runners[spec["name"]] = runner
    return runners


def _token_alive(url: str, token: str) -> bool:
    """发一次空心跳探测令牌是否仍然有效。"""
    try:
        _request(url, "POST", "/api/v1/report", {"ts": datetime.now().astimezone().isoformat(timespec="milliseconds")}, token)
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




def _backfill_history(url: str, session: str, token: str, runner: dict[str, Any], spec: dict[str, Any]) -> None:
    """首次运行时通过 /report 补齐 180 天日线权益，便于总览/详情立即看到风险指标。"""
    detail = _request(url, "GET", "/api/v1/runners/" + str(runner["id"]), token=session)
    if len(detail.get("equity") or []) >= 100:
        return
    target = float(spec["initial_equity"])
    rnd = random.Random("history-" + spec["name"])
    values = [target * 0.78]
    for _ in range(179):
        values.append(values[-1] * (1 + rnd.gauss(0.0018, 0.007)))
    scale = target / values[-1]
    values = [round(value * scale, 2) for value in values]
    now = datetime.now().astimezone()
    base = values[0]
    for index, value in enumerate(values):
        day = now - timedelta(days=179 - index)
        ts = day.replace(hour=15, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        _request(url, "POST", "/api/v1/report", {
            "ts": ts, "equity": value,
            "pnl": round(value - base, 2),
            "nav": round(value / base, 6),
        }, token)
    print(f"补齐历史权益 {spec['name']}：{len(values)} 天，当前 {target:,.2f} CNY")

def ensure_tokens(url: str, session: str, runners: dict[str, dict[str, Any]]) -> dict[str, str]:
    """复用 data/sim_tokens.json 中有效的令牌，缺失或失效则重新创建；返回 name -> token。"""
    cache = _load_token_cache()
    same_server = cache.get("url") == url
    cached_strategies: dict[str, Any] = (cache.get("strategies") or {}) if same_server else {}
    tokens: dict[str, str] = {}
    for spec in STRATEGIES:
        runner = runners[spec["name"]]
        cached = cached_strategies.get(spec["name"]) or {}
        token = str(cached.get("token") or "")
        if token and cached.get("runner_id") == runner["id"] and _token_alive(url, token):
            tokens[spec["name"]] = token
            print(f"复用令牌 {spec['name']}（{token[:7]}…{token[-4:]}）")
            continue
        created = _request(
            url, "POST", "/api/v1/tokens",
            {
                "name": spec["name"] + " · 模拟器",
                "runner_id": runner["id"],
                "platform": spec["platform"],
                "markets": [spec["market"]],
                "note": "sim/run.py 自动创建",
            },
            token=session,
        )
        tokens[spec["name"]] = str(created["token"])
        cached_strategies[spec["name"]] = {"runner_id": runner["id"], "token": created["token"]}
        print(f"创建令牌 {spec['name']}（{created['record']['token_prefix']}）")

    _save_token_cache({
        "url": url,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "strategies": cached_strategies,
    })
    print(f"令牌已保存到 {TOKENS_PATH}")
    return tokens


# ---------- 模拟线程 ----------

def _emit_signal(
    q: Qwatch, spec: dict[str, Any], position: tuple[str, int] | None, rnd: random.Random
) -> tuple[str, int] | None:
    """按当前持仓状态生成一个合理信号，返回更新后的持仓。"""
    code, base_price = rnd.choice(spec["instruments"])
    price = round(base_price * (1 + rnd.uniform(-0.012, 0.012)), 2)
    if position is None:
        direction = "long" if rnd.random() < spec["long_bias"] else "short"
        action = "open"
        qty = rnd.randint(*spec["qty_range"])
    else:
        direction, held = position
        roll = rnd.random()
        if roll < 0.4:
            action, qty = "close", held
        elif roll < 0.7:
            action, qty = "add", rnd.randint(*spec["qty_range"])
        else:
            action, qty = "reduce", max(1, held // 2)

    q.signal(code, direction, action, qty, price=price, msg=rnd.choice(spec["messages"]))
    print(f"[{spec['name']}] {code} {direction}/{action} {qty} @ {price}")

    if action == "open":
        return direction, qty
    if action == "add":
        return direction, position[1] + qty
    if action == "reduce":
        remaining = position[1] - qty
        return None if remaining <= 0 else (direction, remaining)
    return None


def _run_strategy(spec: dict[str, Any], url: str, token: str, stop: threading.Event) -> None:
    """一个策略一个线程：每 10s tick，每 30s 自动心跳，每 15~45s 信号，定期权益。"""
    rnd = random.Random(f"{spec['name']}-{time.time_ns()}")
    try:
        q = Qwatch(url, token, heartbeat=HEARTBEAT_S)
    except AuthError as exc:
        print(f"[{spec['name']}] 令牌无效，线程退出：{exc}")
        return

    equity = float(spec["initial_equity"])
    pnl_base = float(spec["initial_equity"]) * 0.78
    q.equity(round(equity, 2), pnl=round(equity - pnl_base, 2), nav=round(equity / pnl_base, 6))
    position: tuple[str, int] | None = None
    loops = signal_count = 0
    next_signal = time.monotonic() + rnd.uniform(*spec["signal_seconds"])
    next_equity = time.monotonic() + rnd.uniform(10, 20)
    try:
        while not stop.is_set():
            loops += 1
            q.tick()
            now = time.monotonic()
            if now >= next_signal:
                position = _emit_signal(q, spec, position, rnd)
                signal_count += 1
                next_signal = now + rnd.uniform(*spec["signal_seconds"])
            if now >= next_equity:
                equity = max(1.0, equity * (1 + rnd.gauss(0, 0.001)))
                q.equity(round(equity, 2), pnl=round(equity - pnl_base, 2), nav=round(equity / pnl_base, 6))
                next_equity = now + rnd.uniform(10, 20)
            stop.wait(TICK_S)
    finally:
        q.close()
        stats = q.stats
        print(f"[{spec['name']}] 已停止：loop={loops} 信号={signal_count} 上报={stats['sent']} 失败={stats['failed']}")


# ---------- 入口 ----------

def main() -> int:
    parser = argparse.ArgumentParser(description="qwatch 三策略模拟器")
    parser.add_argument("--duration", type=float, default=0.0, help="运行秒数，0 表示一直运行到 Ctrl+C（便于自测）")
    args = parser.parse_args()

    url = os.environ.get("QWATCH_URL", DEFAULT_URL).rstrip("/")
    password = os.environ.get("QWATCH_PASSWORD", DEFAULT_PASSWORD)
    print(f"连接后端 {url}")
    try:
        session = login(url, password)
        runners = ensure_runners(url, session)
        tokens = ensure_tokens(url, session, runners)
        for spec in STRATEGIES:
            _backfill_history(url, session, tokens[spec["name"]], runners[spec["name"]], spec)
    except RuntimeError as exc:
        print(f"启动失败：{exc}")
        return 1

    stop = threading.Event()
    threads = [
        threading.Thread(
            target=_run_strategy, args=(spec, url, tokens[spec["name"]], stop),
            name="sim-" + spec["name"], daemon=True,
        )
        for spec in STRATEGIES
    ]
    try:
        for thread in threads:
            thread.start()
        print(f"模拟已启动（{len(threads)} 个策略，心跳 {HEARTBEAT_S}s，tick {TICK_S}s）；Ctrl+C 退出。")
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
