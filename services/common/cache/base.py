"""
缓存基础接口

定义所有缓存策略必须实现的统一接口
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
import logging


class CacheInterface(ABC):
    """缓存接口抽象基类"""

    def __init__(self, name: str, ttl: int = 3600):
        """
        初始化缓存接口

        Args:
            name: 缓存实例名称（用于日志和命名空间）
            ttl: 默认过期时间（秒）
        """
        self.name = name
        self.default_ttl = ttl
        self.logger = logging.getLogger(f"cache.{name}")

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            Optional[Any]: 缓存值，不存在或过期返回None
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认TTL

        Returns:
            bool: 是否设置成功
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            bool: 是否删除成功
        """
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """
        检查缓存是否存在

        Args:
            key: 缓存键

        Returns:
            bool: 是否存在
        """
        pass

    @abstractmethod
    def clear(self) -> bool:
        """
        清空所有缓存

        Returns:
            bool: 是否清空成功
        """
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            int: 清理的缓存数量
        """
        pass

    def _get_effective_ttl(self, ttl: Optional[int]) -> int:
        """
        获取有效的TTL值

        Args:
            ttl: 指定的TTL，None使用默认值

        Returns:
            int: 有效的TTL值
        """
        return ttl if ttl is not None else self.default_ttl