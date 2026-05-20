from locust import FastHttpUser, between, events

from config.config_settings import EnvConfig, LoadTestConfig
from read_utils.user_context import assign_user_identity, ensure_runtime_data_loaded
from read_utils.user_context import should_load_on_this_runner
from locust_shape import SeckillRampUpShape

if LoadTestConfig.ENABLE_METRICS_REPORT:
    import config.config  # noqa: F401 - 注册退出时报表监听

if LoadTestConfig.ENABLE_PROMETHEUS:
    import prometheus_exporter  # noqa: F401 - 注册 Prometheus 监听

import read_utils.order_pair_store  # noqa: F401 - 注册订单对落盘监听


def get_scenario_tasks():
    # 按场景懒加载任务集，轻量单接口压测时不导入支付、链路、混合场景代码。
    mode = LoadTestConfig.SCENARIO_MODE
    
    if mode == "single_list_detail":
        from case.Single_interface.gacha_list_detail import CheckGachaListDetail

        return [CheckGachaListDetail]

    if mode == "single_list_lite":
        from case.Single_interface.gacha_list import CheckGachaListLite

        return [CheckGachaListLite]

    if mode == "single_pay":
        from case.Single_interface.pay_order_ten import CheckPayOrder

        return [CheckPayOrder]

    if mode == "single_pay_lite":
        from case.Single_interface.pay_order_ten import CheckPayOrderLite

        return [CheckPayOrderLite]


    if mode == "single_pay_result_lite":
        from case.Single_interface.single_pay_result import CheckPayResultLite

        return [CheckPayResultLite]

    if mode == "flow_pay_result":
        from case.Interface_scenario.gacha_scenario import GachaPayResultFlow

        return [GachaPayResultFlow]

    if mode == "flow_pay_result_lite":
        from case.Single_interface.flow_pay_result import FlowCheckPayResultLite

        return [FlowCheckPayResultLite]

    if mode == "mixed":
        from case.Interface_scenario.mixed_scenario import MixedGachaScenario

        return [MixedGachaScenario]

    raise ValueError(
        "LoadTestConfig.SCENARIO_MODE must be one of: "
        "flow_pay_result, flow_pay_result_lite, mixed, "
        "single_list_lite, single_pay, single_pay_lite, "
        "single_pay_result, single_pay_result_lite"
    )


@events.init.add_listener
def on_locust_init(environment, **kwargs):
    # 本地模式和每个 worker 都只在启动时加载一次运行数据。
    if should_load_on_this_runner(environment):
        ensure_runtime_data_loaded()


class WebsiteUser(FastHttpUser):
    # wait_time = between(LoadTestConfig.WAIT_MIN, LoadTestConfig.WAIT_MAX)
    host = EnvConfig.BASE_URL
    tasks = get_scenario_tasks()
    shape_class = SeckillRampUpShape

    def on_start(self):
        assign_user_identity(self)
