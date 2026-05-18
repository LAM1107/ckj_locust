from copy import deepcopy

from locust import SequentialTaskSet, between, task

from config.config_settings import ApiPaths, EnvConfig, LoadTestConfig
from config.logger import log_debug, log_error
from read_utils.business_metrics import increment_write_request
from read_utils.order_pair_store import record_order_pair


def _build_payload():
    payload = deepcopy(LoadTestConfig.PAY_REQUEST_TEMPLATE)
    if not payload:
        payload = {
            "goodsId": 1,
            "quantity": 1,
            "channel": EnvConfig.CHANNEL,
            "payType": "WECHAT",
        }
    else:
        payload.setdefault("channel", EnvConfig.CHANNEL)
    return payload


def pay_order_once(task_set):
    """✅ 生成真实订单，必须写入（single_pay_result 场景用）"""
    payload = _build_payload()
    increment_write_request()

    with task_set.client.post(
        ApiPaths.WX_PAY,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-User-Token": task_set.user.user_token,
        },
        catch_response=True,
        name=ApiPaths.WX_PAY,
    ) as response:
        if response.status_code != 200:
            log_error(f"pay api returned unexpected status: {response.status_code}")
            response.failure(f"Status: {response.status_code}")
            return None

        try:
            body = response.json()
        except Exception as exc:
            response.failure(f"Invalid JSON: {exc}")
            return None

        real_order_no = body.get("orderNo")
        if not real_order_no:
            response.failure("Missing orderNo in pay response")
            return None

        # ✅ 写入 token + CSV orderNo + 接口返回 orderNo
        record_order_pair(
            task_set.user.user_token,
            task_set.user.order_no,  # CSV 中的 orderNo
            real_order_no
        )

        task_set.user.order_no = real_order_no
        log_debug(f"pay success, orderNo={real_order_no}")
        response.success()
        return real_order_no


def pay_order_once_lite(task_set):
    """❌ 只拿字典数据，不写入（性能压测用）"""
    payload = _build_payload()

    response = task_set.client.post(
        ApiPaths.WX_PAY,
        json=payload,
        headers=task_set.headers,
        name=ApiPaths.WX_PAY,
    )

    if response.status_code != 200:
        return None

    try:
        body = response.json()
    except Exception:
        return None

    real_order_no = body.get("orderNo")
    if not real_order_no:
        return None

    task_set.user.order_no = real_order_no  # ✅ 只更新内存
    return real_order_no


class CheckPayOrder(SequentialTaskSet):
    wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    @task
    def wx_pay(self):
        pay_order_once(self)


class CheckPayOrderLite(SequentialTaskSet):
    wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    def on_start(self):
        self.headers = {
            "Content-Type": "application/json",
            "X-User-Token": self.user.user_token,
        }

    @task
    def wx_pay(self):
        pay_order_once_lite(self)