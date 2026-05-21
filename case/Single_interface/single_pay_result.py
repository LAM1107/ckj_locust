from locust import SequentialTaskSet, between, task

from config.config_settings import ApiPaths, LoadTestConfig
from config.logger import log_debug, log_error
from read_utils.business_metrics import increment_read_request




def query_pay_result_once_lite(task_set):
    order_no = getattr(task_set.user, "order_no", None)

    if not order_no:
        raise RuntimeError("pay result query requires orderNo")

    response = task_set.client.get(
        ApiPaths.PAY_RESULT,
        params={"orderNo": order_no},
        headers=task_set.headers,
        name=ApiPaths.PAY_RESULT,
    )

    if response.status_code != 200:
        return None

    response.success()
    return True



class CheckPayResultLite(SequentialTaskSet):
    wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    def on_start(self):
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Token": self.user.user_token,
        }

    @task
    def query_pay_result(self):
        query_pay_result_once_lite(self)
