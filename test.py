from sshtunnel import SSHTunnelForwarder  # 补上导入

import redis
import os
import csv

class MyIterator:
    def __init__(self, data):
        self.data = data  # 通常需要预先存在整个数据集合
        self.index = 0    # 手动记录当前遍历位置

    def __iter__(self):
        return self  # 返回迭代器对象本身

    def __next__(self):
        # 手动检查并抛出StopIteration异常
        if self.index >= len(self.data):
            raise StopIteration
        value = self.data[self.index]
        self.index += 1  # 手动更新位置
        return value

# 使用迭代器
my_list = [1, 2, 3]
my_iter = MyIterator(my_list)

print("迭代器结果:")
for item in my_iter:
    print(item)
# 也可以使用 next() 函数
# print(next(my_iter)) # 输出 1
# print(next(my_iter)) # 输出 2


# def connect_redis_via_ssh():
#     tunnel = SSHTunnelForwarder(
#         ssh_address_or_host=('122.51.216.39', 22),
#         ssh_username='root',
#         ssh_pkey='C:/Users/Lenovo/.ssh/id_ed25519',
#         remote_bind_address=('172.16.0.15', 7000)
#     )
    
#     tunnel.start()
    
    
#     r = redis.Redis(
#         host='127.0.0.1',
#         port=tunnel.local_bind_port,
#         password='UR7WjysAsIRylQTR',
#         db=0,
#         decode_responses=True,
#         socket_timeout=10
#     )
    
#     if r.ping():
#         print("Redis 连接成功！")
#     else:
#         print("Redis 连接失败")
    
#     return r, tunnel  # 返回连接和隧道，用于后续关闭



# conn, tunnel = connect_redis_via_ssh()
# conn.close()
# tunnel.close()

# data_file = os.path.join(os.getcwd(), "user_data.csv")


# with open(data_file, 'r') as f:
#     reader = csv.DictReader(f)
#     print("CSV 列名:", reader.fieldnames)
#     users = list(reader)


# from queue import Queue

# # 全局队列
# TOKEN_QUEUE = Queue()

# def load_tokens():
#     file = os.path.join(os.getcwd(), "user_token.txt")
#     try:
#         with open(file, "r", encoding="utf-8") as f:
#             reader = csv.reader(f)
#             for row in reader:
#                 if row:
#                     token = row[0].strip()
#                     TOKEN_QUEUE.put(token)  # ✅ 放入队列
#                     print(f"Loaded token: {token[:10]}...")
        
#         print(f"✅ 共加载 {TOKEN_QUEUE.qsize()} 个 token")
#     except FileNotFoundError:
#         print(f"❌ 文件不存在: {file}")
#         # 放入默认 token
#         TOKEN_QUEUE.put(EnvConfig.API_TOKEN)


# load_tokens()

# # 测试取出
# while not TOKEN_QUEUE.empty():
#     token = TOKEN_QUEUE.get()
#     print(token)

