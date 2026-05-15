from pydoc import describe
from redis.cluster import RedisCluster
from sshtunnel import SSHTunnelForwarder

import csv
import json
import random
import string
import os

import sys
import os

def write_file(file_list, keys):
    for file_name, description in file_list:
        file_path = os.path.join(os.getcwd(), file_name)

        if not os.path.exists(file_path):
            print(f"文件不存在，创建: {file_path}")
            open(file_path, "a", encoding="utf-8").close()

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for key in keys:
                    if file_name == "user_token.txt" and "_USER_" in key:
                        f.write(key.split("_USER_", 1)[1] + "\n")
                    else:
                        f.write(key + "\n")

            print(f"{description} 写入到 {file_path}")
        except Exception as e:
            print(f"写入文件 {file_name} 时出错: {e}")



# 移除全局 tunnels 列表和模块级 create_tunnel 调用
# tunnels = []  ← 删除

# 删除这三行（模块导入时执行）：
# create_tunnel(7000, '172.16.0.15', 7000)
# create_tunnel(7001, '172.16.0.15', 7001)
# create_tunnel(7002, '172.16.0.15', 7002)


def create_tunnel(local_port, remote_host, remote_port):
    """创建单个 SSH 隧道"""
    tunnel = SSHTunnelForwarder(
        ssh_address_or_host=('122.51.216.39', 22),
        ssh_username='root',
        ssh_pkey='C:/Users/Lenovo/.ssh/id_ed25519',
        remote_bind_address=(remote_host, remote_port),
        local_bind_address=('127.0.0.1', local_port)
    )
    tunnel.start()
    return tunnel


def address_remap(addr):
    host, port = addr
    mapping = {
        ('172.16.0.15', 7000): ('127.0.0.1', 7000),
        ('172.16.0.15', 7001): ('127.0.0.1', 7001),
        ('172.16.0.15', 7002): ('127.0.0.1', 7002),
    }
    return mapping.get((host, port), (host, port))


def connect_cluster():
    """连接 Redis Cluster（假设隧道已启动）"""
    rc = RedisCluster(
        host='127.0.0.1',
        port=7000,
        password='UR7WjysAsIRylQTR',
        decode_responses=True,
        address_remap=address_remap,
        socket_timeout=10,
    )
    return rc


# =========================
# TOKEN_TEMPLATE 保持不变
# =========================
TOKEN_TEMPLATE = {
    "LoginType": "wx_miniapp",
    "User": {
        "account_type": 1,
        "avatar": "defalut_avatar.png",
        "birthday": 0,
        "country_code": "86",
        "created_at": 1766562487919,
        "description": "",
        "email": "",
        "email_verified": 0,
        "gender": 0,
        "id": 0,
        "last_login_ip": "",
        "last_login_time": 0,
        "last_login_type": "",
        "location": "",
        "login_ip": "219.137.28.22",
        "login_num": 1,
        "login_time": 1766562487919,
        "login_type": "GACHA",
        "mobile": "",
        "nickname": "",
        "password": "",
        "realname": "",
        "reg_time": 1766562487919,
        "roles": "user",
        "status": 0,
        "type": 1,
        "updated_at": 1766562487919,
        "username": ""
    },
    "Oplatform": {
        "created_at": 1766562487919,
        "id": 870,
        "union_id": "",
        "updated_at": 1766562487919,
        "user_id": 0
    },
    "Miniapp": {
        "appid": "wx3055bad817fd56fd",
        "created_at": 1769413856728,
        "id": 651,
        "last_login_ip": "219.137.28.22",
        "last_login_time": 1778137446130,
        "open_id": "",
        "reg_ip": "219.137.28.22",
        "session_key": "",
        "source": "",
        "status": 2,
        "union_id": "",
        "updated_at": 1778137446130
    },
    "Mobile": None
}


def generate_token_key():
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=9))
    return f"user:_USER_v2_{random_str}"


def create_token(user_id, mobile):
    token = json.loads(json.dumps(TOKEN_TEMPLATE))
    token["User"]["id"] = user_id
    token["User"]["mobile"] = mobile
    token["Oplatform"]["user_id"] = user_id
    return token


def redis_write_token():
    """写入 Redis Token（包含 SSH 隧道管理）"""
    tunnels = []  # 函数级局部变量
    
    try:
        # 在函数内部启动隧道
        print("启动 SSH 隧道...")
        tunnels.append(create_tunnel(7000, '172.16.0.15', 7000))
        tunnels.append(create_tunnel(7001, '172.16.0.15', 7001))
        tunnels.append(create_tunnel(7002, '172.16.0.15', 7002))
        print("SSH 隧道启动成功")

        rc = connect_cluster()
        print("Redis Cluster 连接成功！")

        data_file = os.path.join(os.getcwd(), "user_data_500.csv")
        with open(data_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            users = list(reader)

        print(f"准备生成 {len(users)} 个 token...")
        count = 0
        all_keys = []

        for user in users:
            try:
                user_id = int(user['id'])
                mobile = user['mobile']
                token_data = create_token(user_id, mobile)
                token_key = generate_token_key()
                all_keys.append(token_key)

                rc.set(token_key, json.dumps(token_data))
                count += 1

                if count % 100 == 0:
                    print(f"已写入 {count} 个")

            except Exception as e:
                print(f"写入失败: {user}")
                print(e)

        print(f"完成！共写入 {count} 个 token")

        data_file_list = [
            ("token_keys.txt", "原始key数据"),
            ("user_token.txt", "分割后的token")
        ]
        write_file(data_file_list, all_keys)

    finally:
        # 确保隧道一定会被关闭
        print("正在关闭 SSH 隧道...")
        for tunnel in tunnels:
            try:
                tunnel.stop()
            except Exception as e:
                print(f"关闭隧道时出错: {e}")
        print("SSH 隧道已关闭")


def delete_tokens():
    """删除 Redis 中的 token keys（包含 SSH 隧道管理）"""
    tunnels = []  # 函数级局部变量
    
    try:
        # 在函数内部启动隧道
        print("启动 SSH 隧道...")
        tunnels.append(create_tunnel(7000, '172.16.0.15', 7000))
        tunnels.append(create_tunnel(7001, '172.16.0.15', 7001))
        tunnels.append(create_tunnel(7002, '172.16.0.15', 7002))
        print("SSH 隧道启动成功")

        try:
            rc = connect_cluster()
            print("Redis Cluster 连接成功！")
        except Exception as e:
            print(f"Redis 连接失败: {e}")
            return

        files_to_process = [
            ("token_keys.txt", "Token数据"),
            ("user_token.txt", "用户Token")
        ]
        
        total_count = 0
        
        for file_name, description in files_to_process:
            file_path = os.path.join(os.getcwd(), file_name)
            
            if not os.path.exists(file_path):
                print(f"{description}文件不存在: {file_path}")
                continue
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    keys = [line.strip() for line in f.readlines() if line.strip()]
            except Exception as e:
                print(f"读取文件失败 {file_path}: {e}")
                continue
            
            if not keys:
                print(f"{description}: 文件为空，跳过")
                continue
            
            print(f"{description}: 准备删除 {len(keys)} 个 key")
            
            count = 0
            pipe = rc.pipeline()
            for key in keys:
                try:
                    pipe.delete(key)
                    count += 1
                    if count % 100 == 0:
                        pipe.execute()
                        print(f"{description}: 已删除 {count} 个")
                except Exception as e:
                    print(f"{description}: 删除失败: {key}")
                    print(e)
            
            if count % 100 != 0:
                pipe.execute()
            
            print(f"{description}: 完成，共删除 {count} 个 key")
            
            try:
                open(file_path, "w", encoding="utf-8").close()
                print(f"{file_name} 已清空")
            except Exception as e:
                print(f"清空文件失败 {file_path}: {e}")

    finally:
        # 确保隧道一定会被关闭
        print("正在关闭 SSH 隧道...")
        for tunnel in tunnels:
            try:
                tunnel.stop()
            except Exception as e:
                print(f"关闭隧道时出错: {e}")
        print("SSH 隧道已关闭")


if __name__ == "__main__":
    redis_write_token()
    # delete_tokens()