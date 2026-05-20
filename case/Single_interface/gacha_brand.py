import urllib.parse

from locust import SequentialTaskSet, between, task

from config.config_settings import ApiPaths, EnvConfig, LoadTestConfig
from config.logger import log_debug, log_error
from read_utils.business_metrics import increment_read_request


GACHA_BRAND_LIST_URL = f"{ApiPaths.GACHA_BRAND_LIST}?{urllib.parse.urlencode({'page': '1', 'size': '10'})}"




class CheckGachaBrand(SequentialTaskSet):
    # wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    def on_start(self):
        # 轻量单接口压测：固定 URL 和 headers，避免每次请求重复构造对象。
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Token": self.user.user_token,
        }

    @task
    def check_gacha_brand(self):
        # 轻量模式只依赖 Locust 原生 HTTP 统计，不做业务计数和手动响应标记。
        with self.client.get(
            GACHA_BRAND_LIST_URL,
            headers=self.headers,
            name=ApiPaths.GACHA_BRAND_LIST
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status: {response.status_code}, Body: {response.text}")
                return None
        
