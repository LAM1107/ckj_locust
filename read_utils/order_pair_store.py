import csv
import os
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

from locust import events

from config.config_settings import FilePath, LoadTestConfig


ORDER_PAIR_QUEUE = Queue()
_RECORDED_ORDER_PAIRS = Queue()


def _normalize_worker_scope(worker_index=None, worker_count=None):
    if worker_index is None:
        worker_index = int(os.getenv("LOCUST_WORKER_INDEX", "0"))
    if worker_count is None:
        worker_count = int(os.getenv("LOCUST_WORKER_COUNT", "1"))

    worker_index = max(0, int(worker_index))
    worker_count = max(1, int(worker_count))
    return worker_index, worker_count


def _worker_index():
    return os.getenv("LOCUST_WORKER_INDEX", "0")


def _order_pair_dir():
    return Path(os.getcwd()) / FilePath.ORDER_PAIR_DIR


def record_order_pair(token, order_no):
    if not token or not order_no:
        return False
    # 先写入内存队列，退出时再统一落盘，避免支付链路每次请求都做文件 IO。
    _RECORDED_ORDER_PAIRS.put((token, order_no))
    return True


def flush_recorded_order_pairs():
    rows = []
    while True:
        try:
            rows.append(_RECORDED_ORDER_PAIRS.get_nowait())
        except Empty:
            break

    if not rows:
        return None

    output_dir = _order_pair_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"{FilePath.ORDER_PAIR_PREFIX}_worker_{_worker_index()}_{timestamp}.csv"

    with open(output_file, "w", encoding="utf-8", newline="") as file_obj:
        writer = csv.writer(file_obj)
        writer.writerow(["token", "orderNo"])
        writer.writerows(rows)

    print(f"已保存 {len(rows)} 个订单对到 {output_file}")
    return output_file


def load_order_pairs(worker_index=None, worker_count=None):
    input_dir = _order_pair_dir()
    pattern = f"{FilePath.ORDER_PAIR_PREFIX}_worker_*.csv"
    files = sorted(input_dir.glob(pattern)) if input_dir.exists() else []

    if not files:
        if LoadTestConfig.ORDER_PAIR_STRICT_MODE:
            raise FileNotFoundError(f"未找到订单文件: {input_dir / pattern}")
        return 0

    all_pairs = []
    for file_path in files:
        with open(file_path, "r", encoding="utf-8", newline="") as file_obj:
            reader = csv.DictReader(file_obj)
            for row in reader:
                token = (row.get("token") or "").strip()
                order_no = (row.get("orderNo") or "").strip()
                if token and order_no:
                    all_pairs.append((token, order_no))

    if not all_pairs and LoadTestConfig.ORDER_PAIR_STRICT_MODE:
        raise RuntimeError(f"订单文件为空: {input_dir}")

    worker_index, worker_count = _normalize_worker_scope(worker_index, worker_count)
    # 按 worker 分片，避免每个 worker 都重复消费同一批 orderNo。
    selected_pairs = all_pairs[worker_index::worker_count]
    for token, order_no in selected_pairs:
        ORDER_PAIR_QUEUE.put((token, order_no))

    if not selected_pairs and LoadTestConfig.ORDER_PAIR_STRICT_MODE:
        raise RuntimeError(
            f"没有订单对分配给 worker {worker_index}/{worker_count}. "
            "准备更多支付结果或减少 worker 数量."
        )

    print(f"已加载 {len(selected_pairs)} 个订单对 for worker {worker_index}/{worker_count}")
    return len(selected_pairs)


def get_order_pair_nowait():
    return ORDER_PAIR_QUEUE.get_nowait()


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    if not LoadTestConfig.ENABLE_ORDER_PAIR_STORE:
        return

    flush_recorded_order_pairs()
