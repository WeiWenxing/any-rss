"""
文件缓存实现

使用JSON文件存储缓存数据，支持TTL和原子写入
零依赖，只使用Python标准库
"""

import json
import hashlib
import time
import os
import tempfile
from pathlib import Path
from typing import Any, Optional
from .base import CacheInterface


class FileCache(CacheInterface):
    """文件缓存实现"""

    def __init__(self, name: str, ttl: int = 3600, cache_dir: str = "storage/cache"):
        """
        初始化文件缓存

        Args:
            name: 缓存实例名称
            ttl: 默认过期时间（秒）
            cache_dir: 缓存根目录
        """
        super().__init__(name, ttl)

        # 创建缓存目录
        self.cache_dir = Path(cache_dir) / name
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"文件缓存初始化完成: {self.cache_dir}")

    def _get_cache_file(self, key: str) -> Path:
        """
        获取缓存文件路径

        Args:
            key: 缓存键

        Returns:
            Path: 缓存文件路径
        """
        # 使用SHA256哈希避免文件名特殊字符问题
        key_hash = hashlib.sha256(key.encode('utf-8')).hexdigest()
        return self.cache_dir / f"{key_hash}.json"

    def _is_expired(self, cache_data: dict) -> bool:
        """
        检查缓存是否过期

        Args:
            cache_data: 缓存数据字典

        Returns:
            bool: 是否过期
        """
        expires_at = cache_data.get("expires_at", 0)
        return time.time() > expires_at

    def _create_cache_data(self, value: Any, ttl: int) -> dict:
        """
        创建缓存数据结构

        Args:
            value: 缓存值
            ttl: 过期时间（秒）

        Returns:
            dict: 缓存数据字典
        """
        # 处理bytes类型数据
        if isinstance(value, bytes):
            value = value.decode('utf-8')

        current_time = time.time()
        return {
            "data": value,
            "created_at": current_time,
            "expires_at": current_time + ttl
        }

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            cache_file = self._get_cache_file(key)

            if not cache_file.exists():
                self.logger.debug(f"缓存文件不存在: {key}")
                return None

            # 读取缓存文件
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # 检查是否过期
            if self._is_expired(cache_data):
                self.logger.debug(f"缓存已过期: {key}")
                # 删除过期文件
                try:
                    cache_file.unlink()
                except OSError:
                    pass
                return None

            self.logger.debug(f"缓存命中: {key}")
            return cache_data["data"]

        except (json.JSONDecodeError, KeyError, OSError) as e:
            self.logger.error(f"读取缓存失败: {key}, 错误: {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            effective_ttl = self._get_effective_ttl(ttl)
            cache_data = self._create_cache_data(value, effective_ttl)
            cache_file = self._get_cache_file(key)

            # 原子写入：先写临时文件，再重命名
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=self.cache_dir,
                delete=False,
                suffix='.tmp'
            ) as temp_file:
                json.dump(cache_data, temp_file, ensure_ascii=False, indent=2)
                temp_file_path = temp_file.name

            # Windows下先删除目标文件再重命名
            if os.path.exists(cache_file):
                os.remove(cache_file)
            # 原子重命名
            os.rename(temp_file_path, cache_file)

            self.logger.debug(f"缓存设置成功: {key}, TTL: {effective_ttl}秒")
            return True

        except (OSError, TypeError, json.JSONEncodeError) as e:
            # 清理临时文件
            try:
                os.remove(temp_file_path)
            except:
                pass
            self.logger.error(f"设置缓存失败: {key}, 错误: {str(e)}", exc_info=True)
            return False

    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            cache_file = self._get_cache_file(key)

            if cache_file.exists():
                cache_file.unlink()
                self.logger.debug(f"缓存删除成功: {key}")
                return True
            else:
                self.logger.debug(f"缓存不存在: {key}")
                return True  # 不存在也算删除成功

        except OSError as e:
            self.logger.error(f"删除缓存失败: {key}, 错误: {str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            cache_file = self._get_cache_file(key)

            if not cache_file.exists():
                return False

            # 读取并检查是否过期
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            if self._is_expired(cache_data):
                # 删除过期文件
                try:
                    cache_file.unlink()
                except OSError:
                    pass
                return False

            return True

        except (json.JSONDecodeError, KeyError, OSError):
            return False

    def clear(self) -> bool:
        """清空所有缓存"""
        try:
            deleted_count = 0

            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                    deleted_count += 1
                except OSError:
                    continue

            self.logger.info(f"清空缓存完成: 删除了 {deleted_count} 个文件")
            return True

        except Exception as e:
            self.logger.error(f"清空缓存失败: {str(e)}")
            return False

    def cleanup_expired(self) -> int:
        """清理过期缓存"""
        try:
            current_time = time.time()
            cleaned_count = 0

            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)

                    expires_at = cache_data.get("expires_at", 0)
                    if current_time > expires_at:
                        cache_file.unlink()
                        cleaned_count += 1

                except (json.JSONDecodeError, KeyError, OSError):
                    # 损坏的文件也删除
                    try:
                        cache_file.unlink()
                        cleaned_count += 1
                    except OSError:
                        pass

            if cleaned_count > 0:
                self.logger.info(f"清理过期缓存完成: 删除了 {cleaned_count} 个文件")
            else:
                self.logger.debug("没有过期缓存需要清理")

            return cleaned_count

        except Exception as e:
            self.logger.error(f"清理过期缓存失败: {str(e)}")
            return 0