from locust import SequentialTaskSet, between, task

from case.Single_interface.flow_pay_result import query_pay_result_once
from case.Single_interface.gacha_list import gacha_list_once
from case.Single_interface.coupon import coupon_list_once
from case.Single_interface.pay_order_ten import pay_order_once_scenario
from config.config_settings import LoadTestConfig
from read_utils.business_metrics import (
    increment_flow_failed,
    increment_flow_started,
    increment_flow_succeeded,
)


# 链路1：浏览商品列表>查看商品详情>获取优惠券>创建订单>抽卡结果

def run_gacha_pay_result_flow_once(task_set):
    # 只有整条链路完整成功，才记为一次业务成功。
    increment_flow_started()

    if not gacha_list_once(task_set):
        increment_flow_failed()
        return False

    if not coupon_list_once(task_set):
        increment_flow_failed()
        return False

    order_no = pay_order_once_scenario(task_set)
    if not order_no:
        increment_flow_failed()
        return False

    if not query_pay_result_once(task_set):
        increment_flow_failed()
        return False

    increment_flow_succeeded()
    return True


class GachaPayResultFlow(SequentialTaskSet):
    wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)

    @task
    def browse_pay_then_query_result(self):
        run_gacha_pay_result_flow_once(self)
