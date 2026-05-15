
import logging
from config.config_settings import LoadTestConfig

logging.basicConfig(level=getattr(logging, LoadTestConfig.LOG_LEVEL))
logger = logging.getLogger(__name__)




def log_debug(msg):
    """调试日志辅助方法"""
    if LoadTestConfig.DEBUG_MODE:
        logger.info(msg)
        print(msg)

def log_error(msg):
    """错误日志辅助方法"""
    if LoadTestConfig.DEBUG_MODE:
        logger.error(msg)
        print(msg)

