import os


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class EnvConfig:
    
    BASE_URL = "https://data.dev.goods.fun"
    API_TOKEN = "v2_4e1abd85d9c24ce484062303efff6322"
    GUEST_ID = "b851621f07fc46a9a4d54497ef998d02"
    CHANNEL = "MINI_APP"


class ApiPaths:
    
    
    REWARD_BRAND_LIST = "/gacha/reward_brands"
    GOODS_LIST = "/gacha/goods/v2/list"
    GOODS_V3_ONE = "/gacha/v3/user/goods/one/234"
    GOODS_V3_ONE_CARDS = "/gacha/v3/user/goods/one/234/cards"
    GOODS_DETAIL = "/gacha/goods/one/v2/234"
    WX_PAY = "/gacha/pay/wx"
    PAY_RESULT = "/gacha/pay/result"
    COUPON_LIST = "/gacha/coupon/all"
    GACHA_BRAND_LIST = "/gacha/brands"
    GACHA_BRAND_GOODS_LIST = "/gacha/brand/goods/79"
    USER_GOODS_ONE = "/gacha/v2/user/goods/one/234"
    


class LoadTestConfig:
    PAY_REQUEST_TEMPLATE = {}
    WAIT_MIN = 1
    WAIT_MAX = 3
    DEBUG_MODE = False
    LOG_LEVEL = "WARNING"  # INFO, WARNING, ERROR

    # single_list / single_list_lite / single_pay / single_pay_lite /
    # single_pay_result / single_pay_result_lite / flow_pay_result /
    # flow_pay_result_lite / mixed / single_list_detail / single_coupon
    # single_brand / single_reward_brand / single_brand_goods / single_user_goods_one

    SCENARIO_MODE = os.getenv("LOCUST_SCENARIO_MODE", "single_pay_lite").lower()

    # 轻量压测默认关闭 Prometheus；如果需要 /metrics，再设置 LOCUST_ENABLE_PROMETHEUS=true。
    ENABLE_PROMETHEUS = _env_bool("LOCUST_ENABLE_PROMETHEUS", False)

    # 报告和订单落盘默认保留，正式极限发压时可以用环境变量关闭。
    ENABLE_METRICS_REPORT = _env_bool("LOCUST_ENABLE_METRICS_REPORT", False)
    ENABLE_ORDER_PAIR_STORE = _env_bool("LOCUST_ENABLE_ORDER_PAIR_STORE", False)

    TOKEN_STRICT_MODE = True
    ORDER_PAIR_STRICT_MODE = True


class FilePath:
    TOKEN_FILE = os.getenv("LOCUST_TOKEN_FILE", "user_token.txt")
    OPERATION_FILE = "operation.txt"
    REPORT_FILE = "locust_metrics.txt"
    ORDER_PAIR_DIR = os.getenv("LOCUST_ORDER_PAIR_DIR", "order_pairs")
    ORDER_PAIR_PREFIX = "paid_order_pairs"
