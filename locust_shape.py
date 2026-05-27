from locust import LoadTestShape

class SeckillRampUpShape(LoadTestShape):
    """
    10 分钟分段加压：
    0-3 min: 100 users
    3-6 min: 300 users
    6-10 min: 500 users
    """

    stages = [

        # 阶段 1：180-480 秒，200 用户
        {"duration": 180, "users": 200, "spawn_rate": 10},
        
        # 阶段 2：480-720 秒，400 用户
        {"duration": 480, "users": 400, "spawn_rate": 10},

        # 阶段 3：720-900 秒，600 用户
        {"duration": 720, "users": 600, "spawn_rate": 10},
    ]


    # stages = [
    #     # 阶段 1：0-600 秒，100 用户
    #     {"duration": 600, "users": 10, "spawn_rate": 10}
    # ]

    def tick(self):
        run_time = self.get_run_time()

        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]

        # 10 分钟后结束
        return None