import queue
import threading

from locust.runners import LocalRunner, WorkerRunner

from config.config_settings import EnvConfig, LoadTestConfig
from read_utils.order_pair_store import get_order_pair_nowait, load_order_pairs
from read_utils.token_loader import TOKEN_QUEUE, load_tokens


TOKEN_LOAD_LOCK = threading.Lock()
TOKENS_LOADED = False

ORDER_PAIR_LOAD_LOCK = threading.Lock()
ORDER_PAIRS_LOADED = False


def should_load_on_this_runner(environment):
    runner = environment.runner
    return runner is None or isinstance(runner, (LocalRunner, WorkerRunner))


def uses_saved_order_pairs():
    # 只有 single_pay_result 才读取历史 token/orderNo 对。
    return LoadTestConfig.SCENARIO_MODE == "single_pay_result"


def ensure_runtime_data_loaded():
    if uses_saved_order_pairs():
        _ensure_order_pairs_loaded()
    else:
        _ensure_tokens_loaded()


def assign_user_identity(user):
    user.user_token = None
    user.order_no = None

    ensure_runtime_data_loaded()

    if uses_saved_order_pairs():
        # 结果查询模式在启动时给每个用户绑定一组 token/orderNo。
        _assign_order_pair(user)
    else:
        # 其他模式只给每个用户分配 token，orderNo 保存在当前用户内存里。
        _assign_token(user)


def _ensure_tokens_loaded():
    global TOKENS_LOADED
    if TOKENS_LOADED:
        return

    with TOKEN_LOAD_LOCK:
        if not TOKENS_LOADED:
            load_tokens()
            TOKENS_LOADED = True


def _ensure_order_pairs_loaded():
    global ORDER_PAIRS_LOADED
    if ORDER_PAIRS_LOADED:
        return

    with ORDER_PAIR_LOAD_LOCK:
        if not ORDER_PAIRS_LOADED:
            load_order_pairs()
            ORDER_PAIRS_LOADED = True


def _assign_token(user):
    try:
        user.user_token = TOKEN_QUEUE.get_nowait()
    except queue.Empty:
        if LoadTestConfig.TOKEN_STRICT_MODE:
            raise RuntimeError("No available token. Add more tokens or reduce the target user count.")
        user.user_token = EnvConfig.API_TOKEN


def _assign_order_pair(user):
    try:
        user.user_token, user.order_no = get_order_pair_nowait()
    except queue.Empty:
        if LoadTestConfig.ORDER_PAIR_STRICT_MODE:
            raise RuntimeError(
                "No available token/orderNo pair. Run single_pay first or prepare pair files."
            )
        user.user_token = EnvConfig.API_TOKEN
        user.order_no = None
