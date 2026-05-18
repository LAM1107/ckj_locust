import csv
import os
import threading
from queue import Queue

from config.config_settings import EnvConfig, FilePath, LoadTestConfig


TOKEN_QUEUE = Queue()
TOKEN_POOL = []
TOKEN_POOL_LOCK = threading.Lock()
TOKEN_POOL_INDEX = 0


def _normalize_worker_scope(worker_index=None, worker_count=None):
    if worker_index is None:
        worker_index = int(os.getenv("LOCUST_WORKER_INDEX", "0"))
    if worker_count is None:
        worker_count = int(os.getenv("LOCUST_WORKER_COUNT", "1"))

    worker_index = max(0, int(worker_index))
    worker_count = max(1, int(worker_count))
    return worker_index, worker_count


def load_tokens(worker_index=None, worker_count=None):
    global TOKEN_POOL_INDEX

    file_path = os.path.join(os.getcwd(), FilePath.TOKEN_FILE)
    worker_index, worker_count = _normalize_worker_scope(worker_index, worker_count)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            tokens = [row[0].strip() for row in reader if row and row[0].strip()]
    except FileNotFoundError:
        if LoadTestConfig.TOKEN_STRICT_MODE:
            raise FileNotFoundError(f"token文件不存在: {file_path}")
        tokens = [EnvConfig.API_TOKEN]

    if worker_count > 1:
        tokens = tokens[worker_index::worker_count]

    TOKEN_POOL.clear()
    TOKEN_POOL.extend(tokens)
    TOKEN_POOL_INDEX = 0

    for token in tokens:
        TOKEN_QUEUE.put(token)

    print(f"加载 {len(tokens)} 个token,用于worker {worker_index}/{worker_count}")
    return len(tokens)


def get_reusable_token():
    global TOKEN_POOL_INDEX

    if not TOKEN_POOL:
        raise IndexError("没有可用的token，请先加载token。")

    with TOKEN_POOL_LOCK:
        token = TOKEN_POOL[TOKEN_POOL_INDEX % len(TOKEN_POOL)]
        TOKEN_POOL_INDEX += 1
        return token


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
