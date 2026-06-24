#!/usr/bin/env python3
import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    kind: str
    target: str
    timeout: float


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    return int(value)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def optional_context() -> str:
    lines: list[str] = []

    deploy_info = os.getenv("MONITOR_DEPLOY_INFO", "").strip()
    if deploy_info:
        lines.append(deploy_info)

    deploy_info_file = os.getenv("MONITOR_DEPLOY_INFO_FILE", "").strip()
    if deploy_info_file:
        path = Path(deploy_info_file)
        if path.exists():
            file_text = path.read_text().strip()
            if file_text:
                lines.append(file_text)

    if not lines:
        return ""
    return "\n\nContext:\n" + "\n".join(f"- {line}" for line in lines)


def parse_tcp_checks(default_host: str, raw: str) -> list[Check]:
    checks: list[Check] = []
    if not raw.strip():
        return checks

    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue

        parts = item.split(":")
        if len(parts) == 2:
            port, name = parts
            host = default_host
        elif len(parts) == 3:
            host, port, name = parts
        else:
            raise ValueError(f"Invalid TCP_CHECKS item: {item}")

        checks.append(Check(name=name, kind="tcp", target=f"{host}:{int(port)}", timeout=5.0))
    return checks


def parse_http_checks(raw: str) -> list[Check]:
    checks: list[Check] = []
    if not raw.strip():
        return checks

    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue

        name, sep, url = item.partition("=")
        if not sep:
            raise ValueError(f"Invalid HTTP_CHECKS item: {item}")
        checks.append(Check(name=name.strip(), kind="http", target=url.strip(), timeout=8.0))
    return checks


def tcp_check(target: str, timeout: float) -> tuple[bool, str]:
    host, port_text = target.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port_text)))
        return True, "ok"
    except OSError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    finally:
        sock.close()


def http_check(url: str, timeout: float) -> tuple[bool, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "server-monitor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if 200 <= response.status < 300:
                return True, f"HTTP {response.status}"
            return False, f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


def run_checks(checks: list[Check]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    for check in checks:
        if check.kind == "tcp":
            ok, detail = tcp_check(check.target, check.timeout)
        elif check.kind == "http":
            ok, detail = http_check(check.target, check.timeout)
        else:
            ok, detail = False, f"unknown check kind: {check.kind}"

        if not ok:
            failures.append(f"{check.name}: {detail}")

    return not failures, failures


def load_state(path: Path) -> dict:
    if not path.exists():
        return {
            "status": "unknown",
            "fail_count": 0,
            "recover_count": 0,
            "down_since": None,
            "last_failures": [],
        }
    return json.loads(path.read_text())


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(path)


def send_notification(title: str, message: str) -> None:
    notify_url = os.getenv("NOTIFY_API_URL", "").strip()
    notify_token = os.getenv("NOTIFY_API_TOKEN", "").strip()
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    errors: list[str] = []

    if telegram_token and telegram_chat_id:
        api_base = os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org").rstrip("/")
        payload = {
            "chat_id": telegram_chat_id,
            "text": f"{title}\n\n{message}",
            "disable_web_page_preview": True,
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{api_base}/bot{telegram_token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                response.read()
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"telegram: {type(exc).__name__}: {exc}")

    if notify_url and notify_token:
        payload = {
            "type": "critical" if "DOWN" in title else "info",
            "title": title,
            "message": message,
            "source": os.getenv("MONITOR_NAME", "server-monitor"),
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            notify_url,
            data=data,
            headers={
                "Authorization": f"Bearer {notify_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                response.read()
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            errors.append(f"notify-api: {type(exc).__name__}: {exc}")

    if errors:
        raise RuntimeError("; ".join(errors))
    raise RuntimeError("no notification channel configured")


def maybe_notify(state: dict, ok: bool, failures: list[str]) -> dict:
    name = os.getenv("MONITOR_NAME", "server")
    fail_threshold = env_int("MONITOR_FAIL_THRESHOLD", 3)
    recover_threshold = env_int("MONITOR_RECOVER_THRESHOLD", 2)
    context = optional_context()

    if ok:
        state["fail_count"] = 0
        state["recover_count"] = state.get("recover_count", 0) + 1
        should_notify_recovery = state.get("down_alert_sent", False)
        if state.get("status") == "down" and state["recover_count"] >= recover_threshold:
            down_since = state.get("down_since") or "unknown"
            if should_notify_recovery:
                try:
                    send_notification(
                        f"✅ {name} RECOVERED",
                        f"All checks are healthy.\nDown since: {down_since}\nRecovered at: {now_iso()}{context}",
                    )
                    state["last_notify_error"] = None
                except RuntimeError as exc:
                    state["last_notify_error"] = str(exc)
            state["status"] = "up"
            state["down_since"] = None
            state["down_alert_sent"] = False
        elif state.get("status") == "unknown":
            state["status"] = "up"
            state["down_alert_sent"] = False
        state["last_failures"] = []
        return state

    state["recover_count"] = 0
    state["fail_count"] = state.get("fail_count", 0) + 1
    state["last_failures"] = failures
    if state.get("status") != "down" and state["fail_count"] >= fail_threshold:
        state["status"] = "down"
        state["down_since"] = now_iso()
        state["down_alert_sent"] = False
        try:
            send_notification(
                f"🚨 {name} DOWN",
                "Failed checks:\n" + "\n".join(f"- {failure}" for failure in failures) + context,
            )
            state["last_notify_error"] = None
            state["down_alert_sent"] = True
        except RuntimeError as exc:
            state["last_notify_error"] = str(exc)
    return state


def main() -> None:
    default_host = os.environ["TARGET_HOST"]
    checks = parse_tcp_checks(default_host, os.getenv("TCP_CHECKS", "22:ssh"))
    checks.extend(parse_http_checks(os.getenv("HTTP_CHECKS", "")))
    if not checks:
        raise RuntimeError("No checks configured")

    state_path = Path(os.getenv("MONITOR_STATE_FILE", "/var/lib/server-monitor/state.json"))
    interval = env_int("MONITOR_INTERVAL_SECONDS", 60)
    once = os.getenv("MONITOR_ONCE", "").lower() in {"1", "true", "yes"}

    while True:
        state = load_state(state_path)
        ok, failures = run_checks(checks)
        state["checked_at"] = now_iso()
        state = maybe_notify(state, ok, failures)
        save_state(state_path, state)
        print(json.dumps({"ok": ok, "failures": failures, "state": state}, ensure_ascii=False), flush=True)
        if once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
