import csv
import os
import threading
from datetime import datetime

from locust import events

from config.config_settings import FilePath, LoadTestConfig


_RECORDED_ORDER_PAIRS = []
_RECORD_LOCK = threading.Lock()


def _worker_index():
    return os.getenv("LOCUST_WORKER_INDEX", "0")


def record_order_pair(user_token, csv_order_no, real_order_no):
    if not user_token or not csv_order_no or not real_order_no:
        return False
    with _RECORD_LOCK:
        _RECORDED_ORDER_PAIRS.append((user_token, csv_order_no, real_order_no))
    return True


def flush_recorded_order_pairs():
    with _RECORD_LOCK:
        if not _RECORDED_ORDER_PAIRS:
            return None
        rows = _RECORDED_ORDER_PAIRS.copy()
        _RECORDED_ORDER_PAIRS.clear()

    worker_index = _worker_index()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"order_pair_used_{worker_index}_{timestamp}.csv"

    with open(filename, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["token", "csv_order_no", "real_order_no"])
        writer.writerows(rows)

    print(f"已保存 {len(rows)} 个订单对到 {filename}")
    return filename


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    if not LoadTestConfig.ENABLE_ORDER_PAIR_STORE:
        return
    flush_recorded_order_pairs()
