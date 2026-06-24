import importlib.util
from pathlib import Path


def load_monitor_module():
    path = Path(__file__).resolve().parents[1] / "monitor" / "server_monitor.py"
    spec = importlib.util.spec_from_file_location("server_monitor", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_recovery_is_not_notified_when_down_alert_was_not_sent(monkeypatch):
    monitor = load_monitor_module()
    notifications = []

    def fail_notification(title, message):
        notifications.append((title, message))
        raise RuntimeError("notification channel unavailable")

    monkeypatch.setenv("MONITOR_FAIL_THRESHOLD", "1")
    monkeypatch.setenv("MONITOR_RECOVER_THRESHOLD", "1")
    monkeypatch.setattr(monitor, "send_notification", fail_notification)

    state = {
        "status": "up",
        "fail_count": 0,
        "recover_count": 0,
        "down_since": None,
        "last_failures": [],
    }

    state = monitor.maybe_notify(state, ok=False, failures=["ssh: timeout"])
    assert state["status"] == "down"
    assert state["down_alert_sent"] is False
    assert len(notifications) == 1

    def unexpected_notification(title, message):
        raise AssertionError("recovery notification should not be sent")

    monkeypatch.setattr(monitor, "send_notification", unexpected_notification)
    state = monitor.maybe_notify(state, ok=True, failures=[])

    assert state["status"] == "up"
    assert state["down_alert_sent"] is False


def test_recovery_is_notified_after_sent_down_alert(monkeypatch):
    monitor = load_monitor_module()
    notifications = []

    monkeypatch.setenv("MONITOR_FAIL_THRESHOLD", "1")
    monkeypatch.setenv("MONITOR_RECOVER_THRESHOLD", "1")
    monkeypatch.setattr(monitor, "send_notification", lambda title, message: notifications.append((title, message)))

    state = {
        "status": "up",
        "fail_count": 0,
        "recover_count": 0,
        "down_since": None,
        "last_failures": [],
    }

    state = monitor.maybe_notify(state, ok=False, failures=["ssh: timeout"])
    state = monitor.maybe_notify(state, ok=True, failures=[])

    assert [title for title, _ in notifications] == ["🚨 server DOWN", "✅ server RECOVERED"]
    assert state["status"] == "up"
    assert state["down_alert_sent"] is False
