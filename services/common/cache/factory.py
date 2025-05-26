"""
缓存工厂

根据配置创建合适的缓存实例，支持多种缓存策略
"""

import os
import logging
from typing import Optional, Dict, Any
from .base import CacheInterface
from .file_cache import FileCache

# 尝试导入Redis缓存
try:
    from .redis_cache import RedisCache
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger("cache.factory")


def get_cache(name: str,
              cache_type: Optional[str] = None,
              ttl: int = 3600,
              **kwargs) -> CacheInterface:
    """
    获取缓存实例

    Args:
        name: 缓存实例名称
        cache_type: 缓存类型 ('file', 'redis', None=自动选择)
        ttl: 默认过期时间（秒）
        **kwargs: 缓存特定的配置参数

    Returns:
        CacheInterface: 缓存实例

    Raises:
        ValueError: 不支持的缓存类型
        ImportError: 缺少必要的依赖
    """
    # 自动选择缓存类型
    if cache_type is None:
        cache_type = _get_default_cache_type()

    cache_type = cache_type.lower()

    logger.info(f"创建缓存实例: {name}, 类型: {cache_type}")

    if cache_type == "file":
        return _create_file_cache(name, ttl, **kwargs)
    elif cache_type == "redis":
        return _create_redis_cache(name, ttl, **kwargs)
    else:
        raise ValueError(f"不支持的缓存类型: {cache_type}")


def _get_default_cache_type() -> str:
    """
    获取默认缓存类型

    优先级：
    1. 环境变量 CACHE_TYPE
    2. Redis可用且有配置 -> redis
    3. 默认 -> file

    Returns:
        str: 缓存类型
    """
    # 检查环境变量
    env_cache_type = os.getenv("CACHE_TYPE", "").lower()
    if env_cache_type in ["file", "redis"]:
        logger.debug(f"使用环境变量指定的缓存类型: {env_cache_type}")
        return env_cache_type

    # 检查Redis可用性和配置
    if REDIS_AVAILABLE and _has_redis_config():
        logger.debug("检测到Redis配置，使用Redis缓存")
        return "redis"

    # 默认使用文件缓存
    logger.debug("使用默认文件缓存")
    return "file"


def _has_redis_config() -> bool:
    """
    检查是否有Redis配置

    Returns:
        bool: 是否有Redis配置
    """
    redis_host = os.getenv("REDIS_HOST")
    redis_url = os.getenv("REDIS_URL")

    return bool(redis_host or redis_url)


def _create_file_cache(name: str, ttl: int, **kwargs) -> FileCache:
    """
    创建文件缓存实例

    Args:
        name: 缓存名称
        ttl: 过期时间
        **kwargs: 文件缓存配置

    Returns:
        FileCache: 文件缓存实例
    """
    # 从环境变量或kwargs获取配置
    cache_dir = kwargs.get("cache_dir") or os.getenv("CACHE_DIR", "storage/cache")

    return FileCache(
        name=name,
        ttl=ttl,
        cache_dir=cache_dir
    )


def _create_redis_cache(name: str, ttl: int, **kwargs) -> RedisCache:
    """
    创建Redis缓存实例

    Args:
        name: 缓存名称
        ttl: 过期时间
        **kwargs: Redis配置

    Returns:
        RedisCache: Redis缓存实例

    Raises:
        ImportError: Redis不可用
        ConnectionError: Redis连接失败时降级到文件缓存
    """
    if not REDIS_AVAILABLE:
        logger.warning("Redis不可用，降级到文件缓存")
        return _create_file_cache(name, ttl, **kwargs)

    # 获取Redis配置
    redis_config = _get_redis_config(**kwargs)

    try:
        return RedisCache(name=name, ttl=ttl, **redis_config)
    except Exception as e:
        logger.error(f"Redis缓存创建失败: {str(e)}")

        # 检查是否允许降级
        allow_fallback = kwargs.get("allow_fallback", True)
        if allow_fallback:
            logger.warning("降级到文件缓存")
            return _create_file_cache(name, ttl, **kwargs)
        else:
            raise


def _get_redis_config(**kwargs) -> Dict[str, Any]:
    """
    获取Redis配置

    优先级：
    1. kwargs参数
    2. 环境变量
    3. 默认值

    Returns:
        Dict[str, Any]: Redis配置字典
    """
    config = {}

    # Redis URL（优先级最高）
    redis_url = kwargs.get("redis_url") or os.getenv("REDIS_URL")
    if redis_url:
        # 解析Redis URL
        try:
            import redis
            connection_pool = redis.ConnectionPool.from_url(redis_url)
            connection_kwargs = connection_pool.connection_kwargs

            # 只提取基本连接参数，避免冲突
            config.update({
                "host": connection_kwargs.get("host", "localhost"),
                "port": connection_kwargs.get("port", 6379),
                "db": connection_kwargs.get("db", 0),
                "password": connection_kwargs.get("password"),
            })
        except Exception as e:
            logger.warning(f"解析Redis URL失败: {str(e)}")

    # 单独的配置参数（只在URL未提供时使用）
    if not redis_url:
        config.update({
            "host": kwargs.get("host") or os.getenv("REDIS_HOST", "localhost"),
            "port": int(kwargs.get("port") or os.getenv("REDIS_PORT", 6379)),
            "db": int(kwargs.get("db") or os.getenv("REDIS_DB", 0)),
            "password": kwargs.get("password") or os.getenv("REDIS_PASSWORD"),
        })

    # 其他配置（总是添加，但避免重复）
    additional_config = {
        "decode_responses": kwargs.get("decode_responses", True),
        "socket_connect_timeout": kwargs.get("socket_connect_timeout", 5),
        "socket_timeout": kwargs.get("socket_timeout", 5),
    }

    # 只添加不冲突的配置
    for key, value in additional_config.items():
        if key not in config:
            config[key] = value

    # 移除None值
    config = {k: v for k, v in config.items() if v is not None}

    logger.debug(f"Redis配置: {_mask_password(config)}")
    return config


def _mask_password(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    遮蔽密码用于日志输出

    Args:
        config: 配置字典

    Returns:
        Dict[str, Any]: 遮蔽密码后的配置
    """
    masked_config = config.copy()
    if "password" in masked_config and masked_config["password"]:
        masked_config["password"] = "***"
    return masked_config


def get_cache_info(cache: CacheInterface) -> Dict[str, Any]:
    """
    获取缓存信息

    Args:
        cache: 缓存实例

    Returns:
        Dict[str, Any]: 缓存信息
    """
    try:
        # 尝试调用get_info方法（Redis缓存有此方法）
        if hasattr(cache, 'get_info'):
            return cache.get_info()

        # 文件缓存的基本信息
        return {
            "type": "file",
            "name": cache.name,
            "default_ttl": cache.default_ttl
        }

    except Exception as e:
        logger.error(f"获取缓存信息失败: {str(e)}")
        return {"error": str(e)}


# 全局缓存实例管理
_cache_instances: Dict[str, CacheInterface] = {}


def get_shared_cache(name: str, **kwargs) -> CacheInterface:
    """
    获取共享缓存实例（单例模式）

    Args:
        name: 缓存名称
        **kwargs: 缓存配置

    Returns:
        CacheInterface: 缓存实例
    """
    if name not in _cache_instances:
        _cache_instances[name] = get_cache(name, **kwargs)

    return _cache_instances[name]


def close_all_caches():
    """关闭所有缓存连接"""
    for name, cache in _cache_instances.items():
        try:
            if hasattr(cache, 'close'):
                cache.close()
                logger.info(f"缓存连接已关闭: {name}")
        except Exception as e:
            logger.error(f"关闭缓存连接失败: {name}, 错误: {str(e)}")

    _cache_instances.clear()