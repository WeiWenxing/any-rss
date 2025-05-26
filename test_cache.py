#!/usr/bin/env python3
"""
缓存系统测试脚本

测试文件缓存和Redis缓存的基本功能
"""

import os
import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.common.cache import get_cache
from services.common.cache.factory import get_cache_info, close_all_caches

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("cache_test")


def test_cache_basic_operations(cache_type: str):
    """
    测试缓存基本操作

    Args:
        cache_type: 缓存类型 ('file' 或 'redis')
    """
    logger.info(f"开始测试 {cache_type} 缓存基本操作")
    
    try:
        # 创建缓存实例
        cache = get_cache("test", cache_type=cache_type, ttl=10)
        
        # 测试数据
        test_data = {
            "string": "Hello, World!",
            "number": 42,
            "list": [1, 2, 3, "test"],
            "dict": {"key": "value", "nested": {"a": 1}}
        }
        
        # 测试设置和获取
        for key, value in test_data.items():
            logger.info(f"设置缓存: {key} = {value}")
            success = cache.set(key, value)
            assert success, f"设置缓存失败: {key}"
            
            retrieved = cache.get(key)
            assert retrieved == value, f"获取缓存失败: {key}, 期望: {value}, 实际: {retrieved}"
            logger.info(f"获取缓存成功: {key}")
        
        # 测试存在性检查
        assert cache.exists("string"), "exists检查失败"
        assert not cache.exists("nonexistent"), "不存在的键exists检查失败"
        
        # 测试删除
        success = cache.delete("string")
        assert success, "删除缓存失败"
        assert not cache.exists("string"), "删除后exists检查失败"
        assert cache.get("string") is None, "删除后仍能获取到值"
        
        # 测试TTL
        cache.set("ttl_test", "will_expire", ttl=2)
        assert cache.get("ttl_test") == "will_expire", "TTL测试设置失败"
        
        logger.info("等待2秒测试TTL...")
        time.sleep(3)
        
        assert cache.get("ttl_test") is None, "TTL测试失败，缓存未过期"
        
        # 测试清空
        cache.set("clear_test1", "value1")
        cache.set("clear_test2", "value2")
        success = cache.clear()
        assert success, "清空缓存失败"
        assert cache.get("clear_test1") is None, "清空后仍能获取到值"
        assert cache.get("clear_test2") is None, "清空后仍能获取到值"
        
        logger.info(f"{cache_type} 缓存基本操作测试通过 ✓")
        
        # 显示缓存信息
        info = get_cache_info(cache)
        logger.info(f"缓存信息: {info}")
        
    except Exception as e:
        logger.error(f"{cache_type} 缓存测试失败: {str(e)}")
        raise


def test_file_cache():
    """测试文件缓存"""
    test_cache_basic_operations("file")


def test_redis_cache():
    """测试Redis缓存"""
    try:
        test_cache_basic_operations("redis")
    except ImportError:
        logger.warning("Redis库未安装，跳过Redis缓存测试")
    except Exception as e:
        if "Redis连接失败" in str(e):
            logger.warning("Redis服务未运行，跳过Redis缓存测试")
        else:
            raise


def test_cache_factory():
    """测试缓存工厂"""
    logger.info("测试缓存工厂")
    
    # 测试默认缓存（应该是文件缓存）
    cache1 = get_cache("factory_test1")
    cache1.set("test", "value1")
    assert cache1.get("test") == "value1"
    
    # 测试指定类型
    cache2 = get_cache("factory_test2", cache_type="file")
    cache2.set("test", "value2")
    assert cache2.get("test") == "value2"
    
    logger.info("缓存工厂测试通过 ✓")


def test_environment_config():
    """测试环境变量配置"""
    logger.info("测试环境变量配置")
    
    # 保存原始环境变量
    original_cache_type = os.getenv("CACHE_TYPE")
    
    try:
        # 设置环境变量
        os.environ["CACHE_TYPE"] = "file"
        cache = get_cache("env_test")
        cache.set("env_test", "success")
        assert cache.get("env_test") == "success"
        
        logger.info("环境变量配置测试通过 ✓")
        
    finally:
        # 恢复原始环境变量
        if original_cache_type is not None:
            os.environ["CACHE_TYPE"] = original_cache_type
        elif "CACHE_TYPE" in os.environ:
            del os.environ["CACHE_TYPE"]


def main():
    """主测试函数"""
    logger.info("开始缓存系统测试")
    
    try:
        # 测试文件缓存
        test_file_cache()
        
        # 测试Redis缓存
        test_redis_cache()
        
        # 测试缓存工厂
        test_cache_factory()
        
        # 测试环境变量配置
        test_environment_config()
        
        logger.info("所有缓存测试通过 ✓")
        
    except Exception as e:
        logger.error(f"缓存测试失败: {str(e)}")
        sys.exit(1)
    
    finally:
        # 清理资源
        close_all_caches()
        logger.info("测试完成，资源已清理")


if __name__ == "__main__":
    main() 