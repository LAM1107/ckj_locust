import urllib.parse

from locust import SequentialTaskSet, between, task

from config.config_settings import ApiPaths, EnvConfig, LoadTestConfig
from config.logger import log_debug, log_error
from read_utils.business_metrics import increment_read_request


COUPON_LIST_URL = f"{ApiPaths.COUPON_LIST}"


def coupon_list_once(task_set):
    increment_read_request()
    response = task_set.client.get(
        COUPON_LIST_URL,
        headers={
            "Content-Type": "application/json",
            "X-User-Token": task_set.user.user_token,
        },
        name=ApiPaths.COUPON_LIST,
    )
    if response.status_code == 200:
        return True
    return False

class CheckCoupon(SequentialTaskSet):
    # wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    def on_start(self):
        # 轻量单接口压测：固定 URL 和 headers，避免每次请求重复构造对象。
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Token": self.user.user_token,
        }

    @task
    def check_coupon(self):
        # 轻量模式只依赖 Locust 原生 HTTP 统计，不做业务计数和手动响应标记。
        self.client.get(
            COUPON_LIST_URL,
            headers=self.headers,
            name=ApiPaths.COUPON_LIST
        )
