import urllib.parse

from locust import SequentialTaskSet, between, task

from config.config_settings import ApiPaths, EnvConfig, LoadTestConfig
from config.logger import log_debug, log_error
from read_utils.business_metrics import increment_read_request


USER_GOODS_ONE_URL = f"{ApiPaths.USER_GOODS_ONE}?{urllib.parse.urlencode({'exist': '0'})}"




class CheckUserGoodsOne(SequentialTaskSet):
    # wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    def on_start(self):
        # 轻量单接口压测：固定 URL 和 headers，避免每次请求重复构造对象。
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Token": self.user.user_token,
        }

    @task
    def check_user_goods_one(self):
        # 轻量模式只依赖 Locust 原生 HTTP 统计，不做业务计数和手动响应标记。
        response = self.client.get(
            USER_GOODS_ONE_URL,
            headers=self.headers,
            name=ApiPaths.USER_GOODS_ONE
        )
        
