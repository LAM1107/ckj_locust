import threading

from locust import events
from locust.runners import MasterRunner


_METRIC_KEYS = (
    "flow_started",
    "flow_succeeded",
    "flow_failed",
    "read_request_count",
    "write_request_count",
)

_LOCK = threading.Lock()
_LOCAL_METRICS = {key: 0 for key in _METRIC_KEYS}
_WORKER_METRICS = {}


def _increment(metric_name, delta=1):
    with _LOCK:
        _LOCAL_METRICS[metric_name] += delta


def increment_flow_started():
    _increment("flow_started")


def increment_flow_succeeded():
    _increment("flow_succeeded")


def increment_flow_failed():
    _increment("flow_failed")


def increment_read_request():
    _increment("read_request_count")


def increment_write_request():
    _increment("write_request_count")


def _normalize_metrics(metrics):
    normalized = {key: 0 for key in _METRIC_KEYS}
    for key in _METRIC_KEYS:
        normalized[key] = int(metrics.get(key, 0) or 0)
    return normalized


def _snapshot_local():
    with _LOCK:
        return dict(_LOCAL_METRICS)


def snapshot_metrics(environment=None):
    runner = getattr(environment, "runner", None)
    if isinstance(runner, MasterRunner):
        with _LOCK:
            merged = dict(_LOCAL_METRICS)
            for worker_metrics in _WORKER_METRICS.values():
                for key in _METRIC_KEYS:
                    merged[key] += worker_metrics.get(key, 0)
        return merged
    return _snapshot_local()


@events.report_to_master.add_listener
def on_report_to_master(client_id, data):
    data["business_metrics"] = _snapshot_local()


@events.worker_report.add_listener
def on_worker_report(client_id, data):
    metrics = data.get("business_metrics")
    if not metrics:
        return

    with _LOCK:
        _WORKER_METRICS[client_id] = _normalize_metrics(metrics)
