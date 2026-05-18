import os
import csv
import threading
from locust.runners import LocalRunner, WorkerRunner

from config.config_settings import EnvConfig, FilePath, LoadTestConfig

# ==================== 全局状态 ====================
TOKEN_POOL = []
ORDER_PAIR_POOL = []        # [(token, csv_order_no), ...]
TOKEN_USER_INDEX = 0
ORDER_PAIR_INDEX = 0

TOKENS_LOADED = False
ORDER_PAIRS_LOADED = False

LOAD_LOCK = threading.Lock()
TOKEN_USER_INDEX_LOCK = threading.Lock()


# ==================== 工具函数 ====================
def should_load_on_this_runner(environment):
    runner = environment.runner
    return runner is None or isinstance(runner, (LocalRunner, WorkerRunner))


def uses_saved_order_pairs():
    return LoadTestConfig.SCENARIO_MODE in {"single_pay_result", "single_pay_result_lite", "flow_pay_result_lite"}


def uses_reusable_tokens():
    return LoadTestConfig.SCENARIO_MODE in {"single_list", "single_list_lite"}


def get_worker_scope():
    worker_index = int(os.environ.get("LOCUST_WORKER_INDEX", 0))
    worker_count = int(os.environ.get("LOCUST_WORKER_COUNT", 1))
    return worker_index, worker_count


# ==================== 数据加载 ====================
def ensure_runtime_data_loaded():
    if uses_saved_order_pairs():
        _ensure_order_pairs_loaded()
    else:
        _ensure_tokens_loaded()


def _ensure_tokens_loaded():
    global TOKENS_LOADED, TOKEN_POOL

    if TOKENS_LOADED:
        return

    with LOAD_LOCK:
        if TOKENS_LOADED:
            return

        worker_index, worker_count = get_worker_scope()
        TOKEN_POOL = load_tokens(worker_index, worker_count)
        TOKENS_LOADED = True


def _ensure_order_pairs_loaded():
    global ORDER_PAIRS_LOADED, ORDER_PAIR_POOL

    if ORDER_PAIRS_LOADED:
        return

    with LOAD_LOCK:
        if ORDER_PAIRS_LOADED:
            return

        worker_index, worker_count = get_worker_scope()
        ORDER_PAIR_POOL = load_order_pairs(worker_index, worker_count)
        ORDER_PAIRS_LOADED = True


def load_tokens(worker_index, worker_count):
    file_path = os.path.join(os.getcwd(), FilePath.TOKEN_FILE)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            tokens = [row[0].strip() for row in reader if row and row[0].strip()]
    except FileNotFoundError:
        if LoadTestConfig.TOKEN_STRICT_MODE:
            raise FileNotFoundError(f"token 文件不存在: {file_path}")
        tokens = [EnvConfig.API_TOKEN]

    if worker_count > 1:
        tokens = tokens[worker_index::worker_count]

    return tokens


def load_order_pairs(worker_index, worker_count):
    import glob
    pattern = os.path.join(os.getcwd(), "order_pair_used_*.csv")
    files = sorted(glob.glob(pattern))

    if not files:
        if LoadTestConfig.ORDER_PAIR_STRICT_MODE:
            raise FileNotFoundError(f"未找到订单文件: {pattern}")
        return [(EnvConfig.API_TOKEN, None)]

    all_pairs = []
    for file_path in files:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if len(row) >= 2 and row[0].strip() and row[1].strip():
                    all_pairs.append((row[0].strip(), row[1].strip()))

    if not all_pairs and LoadTestConfig.ORDER_PAIR_STRICT_MODE:
        raise RuntimeError("订单文件为空")

    if worker_count > 1:
        all_pairs = all_pairs[worker_index::worker_count]

    return all_pairs


# ==================== 分配逻辑 ====================
def assign_user_identity(user):
    user.user_token = None
    user.order_no = None  # CSV 中的 orderNo

    ensure_runtime_data_loaded()

    if uses_saved_order_pairs():
        _assign_order_pair(user)
    elif uses_reusable_tokens():
        _assign_reusable_token(user, _next_token_user_index())
    else:
        _assign_token(user, _next_token_user_index())


def _next_token_user_index():
    global TOKEN_USER_INDEX

    with TOKEN_USER_INDEX_LOCK:
        idx = TOKEN_USER_INDEX
        TOKEN_USER_INDEX += 1
        return idx


def _assign_token(user, user_index):
    if not TOKEN_POOL:
        if LoadTestConfig.TOKEN_STRICT_MODE:
            raise RuntimeError("没有可用的 token")
        user.user_token = EnvConfig.API_TOKEN
        return

    if user_index >= len(TOKEN_POOL):
        if LoadTestConfig.TOKEN_STRICT_MODE:
            raise RuntimeError("没有可用的 token，请添加更多 token 或减少目标用户数量。")
        user.user_token = EnvConfig.API_TOKEN
        return

    user.user_token = TOKEN_POOL[user_index]


def _assign_reusable_token(user, user_index):
    if not TOKEN_POOL:
        if LoadTestConfig.TOKEN_STRICT_MODE:
            raise RuntimeError("没有可用的 token")
        user.user_token = EnvConfig.API_TOKEN
        return

    idx = user_index % len(TOKEN_POOL)
    user.user_token = TOKEN_POOL[idx]


def _assign_order_pair(user):
    global ORDER_PAIR_INDEX

    if not ORDER_PAIR_POOL:
        if LoadTestConfig.ORDER_PAIR_STRICT_MODE:
            raise RuntimeError("没有可用的 token/orderNo 对")
        user.user_token = EnvConfig.API_TOKEN
        user.order_no = None
        return

    if ORDER_PAIR_INDEX >= len(ORDER_PAIR_POOL):
        if LoadTestConfig.ORDER_PAIR_STRICT_MODE:
            raise RuntimeError("token/orderNo 已耗尽")
        user.user_token = EnvConfig.API_TOKEN
        user.order_no = None
        return

    token, csv_order_no = ORDER_PAIR_POOL[ORDER_PAIR_INDEX]
    ORDER_PAIR_INDEX += 1

    user.user_token = token
    user.order_no = csv_order_no