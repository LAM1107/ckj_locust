from locust import TaskSet, task

from case.Interface_scenario.gacha_scenario import run_gacha_pay_result_flow_once
from case.Single_interface.gacha_list import gacha_list_once


class MixedGachaScenario(TaskSet):
    @task(80)
    def browse_goods_list(self):
        gacha_list_once(self)

    @task(20)
    def pay_and_query_result(self):
        # 混合场景直接调用原子函数，保证 80/20 只体现在任务选择层。
        run_gacha_pay_result_flow_once(self)
