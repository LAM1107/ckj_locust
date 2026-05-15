import urllib.parse

from locust import SequentialTaskSet, between, task

from config.config_settings import ApiPaths, EnvConfig, LoadTestConfig
from config.logger import log_debug, log_error
from read_utils.business_metrics import increment_read_request


GACHA_LIST_URL = f"{ApiPaths.GOODS_LIST}?{urllib.parse.urlencode({'cursor': '0', 'channel': EnvConfig.CHANNEL})}"


def gacha_list_once(task_set):
    increment_read_request()

    with task_set.client.get(
        GACHA_LIST_URL,
        headers={
            "Content-Type": "application/json",
            "X-User-Token": task_set.user.user_token,
        },
        catch_response=True,
        name=ApiPaths.GOODS_LIST,
    ) as response:
        if response.status_code == 200:
            log_debug(f"user {task_set.user.user_token} gacha list success")
            response.success()
            return True

        log_error(f"user {task_set.user.user_token} gacha list failed: {response.status_code}")
        response.failure(f"Status: {response.status_code}")
        return False


class CheckGachaList(SequentialTaskSet):
    wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    @task
    def xcx_gacha_list(self):
        gacha_list_once(self)


class CheckGachaListLite(SequentialTaskSet):
    wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    def on_start(self):
        # 轻量单接口压测：固定 URL 和 headers，避免每次请求重复构造对象。
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Token": self.user.user_token,
        }

    @task
    def xcx_gacha_list_lite(self):
        # 轻量模式只依赖 Locust 原生 HTTP 统计，不做业务计数和手动响应标记。
        self.client.get(
            GACHA_LIST_URL,
            headers=self.headers,
            name=ApiPaths.GOODS_LIST,
        )
