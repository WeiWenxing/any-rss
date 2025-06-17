"""
Redis缓存实现

使用Redis作为缓存后端，支持分布式缓存和高性能访问
需要安装redis依赖：pip install redis
"""

import json
import time
import os
from typing import Any, Optional
from .base import CacheInterface

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class RedisCache(CacheInterface):
    """Redis缓存实现"""

    def __init__(self, name: str, ttl: int = 3600,
                 host: str = "localhost", port: int = 6379,
                 db: int = 0, password: Optional[str] = None,
                 decode_responses: bool = True, use_json: bool = True, **kwargs):
        """
        初始化Redis缓存

        Args:
            name: 缓存实例名称
            ttl: 默认过期时间（秒）
            host: Redis主机地址
            port: Redis端口
            db: Redis数据库编号
            password: Redis密码
            decode_responses: 是否自动解码响应
            use_json: 是否使用JSON序列化
            **kwargs: 其他Redis连接参数
        """
        if not REDIS_AVAILABLE:
            raise ImportError("Redis缓存需要安装redis库: pip install redis")

        super().__init__(name, ttl)

        # Redis连接配置
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.use_json = use_json

        # 缓存键前缀，避免不同实例冲突
        self.key_prefix = f"cache:{name}:"

        # 创建Redis连接
        try:
            # 检查是否有Redis URL（最简单的方式）
            redis_url = kwargs.get('redis_url') or os.getenv('REDIS_URL')

            if redis_url:
                # 直接使用Redis URL创建连接
                self.redis_client = redis.Redis.from_url(redis_url, decode_responses=decode_responses)
            else:
                # 使用单独参数创建连接
                connection_params = {
                    "host": host,
                    "port": port,
                    "db": db,
                    "password": password,
                    "decode_responses": decode_responses,
                }
                # 添加其他参数
                connection_params.update(kwargs)
                self.redis_client = redis.Redis(**connection_params)

            # 测试连接
            self.redis_client.ping()
            self.logger.info(f"Redis缓存初始化完成: {host}:{port}/{db}")

        except redis.ConnectionError as e:
            self.logger.error(f"Redis连接失败: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Redis初始化失败: {str(e)}")
            raise

    def _get_full_key(self, key: str) -> str:
        """\
        获取完整的缓存键（包含前缀）

        Args:
            key: 原始键

        Returns:
            str: 完整键
        """
        return f"{self.key_prefix}{key}"

    def _serialize_value(self, value: Any) -> str:
        """
        序列化缓存值

        Args:
            value: 要序列化的值

        Returns:
            str: 序列化后的JSON字符串
        """
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            self.logger.error(f"序列化失败: {str(e)}")
            raise

    def _deserialize_value(self, value: str) -> Any:
        """
        反序列化缓存值

        Args:
            value: JSON字符串

        Returns:
            Any: 反序列化后的值
        """
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"反序列化失败: {str(e)}")
            raise

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            full_key = self._get_full_key(key)
            value = self.redis_client.get(full_key)

            if value is None:
                self.logger.debug(f"缓存未命中: {key}")
                return None

            # 根据配置决定是否反序列化
            if self.use_json:
                value = self._deserialize_value(value)

            self.logger.debug(f"缓存命中: {key}")
            return value

        except redis.ConnectionError as e:
            self.logger.error(f"Redis连接错误: {key}, 错误: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"获取缓存失败: {key}, 错误: {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            full_key = self._get_full_key(key)
            effective_ttl = self._get_effective_ttl(ttl)

            # 打印use_json的值
            self.logger.info(f"use_json的值: {self.use_json}")

            # 根据配置决定是否序列化
            if self.use_json:
                value = self._serialize_value(value)

            # 设置缓存（带过期时间）
            result = self.redis_client.setex(full_key, effective_ttl, value)

            if result:
                self.logger.debug(f"缓存设置成功: {key}, TTL: {effective_ttl}秒")
                return True
            else:
                self.logger.warning(f"缓存设置失败: {key}")
                return False

        except redis.ConnectionError as e:
            self.logger.error(f"Redis连接错误: {key}, 错误: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"设置缓存失败: {key}, 错误: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            full_key = self._get_full_key(key)
            result = self.redis_client.delete(full_key)

            if result > 0:
                self.logger.debug(f"缓存删除成功: {key}")
            else:
                self.logger.debug(f"缓存不存在: {key}")

            return True  # Redis delete总是返回成功

        except redis.ConnectionError as e:
            self.logger.error(f"Redis连接错误: {key}, 错误: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"删除缓存失败: {key}, 错误: {str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            full_key = self._get_full_key(key)
            result = self.redis_client.exists(full_key)
            return bool(result)

        except redis.ConnectionError as e:
            self.logger.error(f"Redis连接错误: {key}, 错误: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"检查缓存失败: {key}, 错误: {str(e)}")
            return False

    def clear(self) -> bool:
        """清空所有缓存"""
        try:
            # 使用模式匹配删除所有带前缀的键
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)

            if keys:
                deleted_count = self.redis_client.delete(*keys)
                self.logger.info(f"清空缓存完成: 删除了 {deleted_count} 个键")
            else:
                self.logger.info("没有缓存需要清空")

            return True

        except redis.ConnectionError as e:
            self.logger.error(f"Redis连接错误: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"清空缓存失败: {str(e)}")
            return False

    def cleanup_expired(self) -> int:
        """
        清理过期缓存

        注意：Redis会自动清理过期键，这个方法主要用于统计
        """
        try:
            # Redis自动处理过期键，这里只是为了接口一致性
            # 实际上我们无法直接统计清理了多少过期键
            self.logger.debug("Redis自动处理过期键清理")
            return 0

        except Exception as e:
            self.logger.error(f"清理过期缓存失败: {str(e)}")
            return 0

    def get_info(self) -> dict:
        """
        获取Redis缓存信息

        Returns:
            dict: 缓存统计信息
        """
        try:
            info = self.redis_client.info()
            pattern = f"{self.key_prefix}*"
            keys_count = len(self.redis_client.keys(pattern))

            return {
                "type": "redis",
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "keys_count": keys_count,
                "memory_usage": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime": info.get("uptime_in_seconds", 0)
            }

        except Exception as e:
            self.logger.error(f"获取Redis信息失败: {str(e)}")
            return {"type": "redis", "error": str(e)}

    def close(self):
        """关闭Redis连接"""
        try:
            if hasattr(self, 'redis_client'):
                self.redis_client.close()
                self.logger.info("Redis连接已关闭")
        except Exception as e:
            self.logger.error(f"关闭Redis连接失败: {str(e)}")