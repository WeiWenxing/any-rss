"""
缓存管理工具

提供缓存状态查看、清理、迁移等管理功能
"""

import logging
from typing import Dict, Any, List
from .factory import get_cache, get_cache_info, get_shared_cache, close_all_caches

logger = logging.getLogger("cache.management")


class CacheManager:
    """缓存管理器"""

    def __init__(self):
        """初始化缓存管理器"""
        self.logger = logging.getLogger("cache.manager")

    def get_all_cache_info(self) -> Dict[str, Any]:
        """
        获取所有缓存实例的信息

        Returns:
            Dict[str, Any]: 缓存信息汇总
        """
        try:
            from .factory import _cache_instances
            
            info = {
                "total_instances": len(_cache_instances),
                "instances": {}
            }
            
            for name, cache in _cache_instances.items():
                try:
                    cache_info = get_cache_info(cache)
                    info["instances"][name] = cache_info
                except Exception as e:
                    info["instances"][name] = {"error": str(e)}
            
            return info
            
        except Exception as e:
            self.logger.error(f"获取缓存信息失败: {str(e)}")
            return {"error": str(e)}

    def clear_cache(self, cache_name: str) -> bool:
        """
        清空指定缓存

        Args:
            cache_name: 缓存名称

        Returns:
            bool: 是否成功
        """
        try:
            cache = get_shared_cache(cache_name)
            success = cache.clear()
            
            if success:
                self.logger.info(f"缓存清空成功: {cache_name}")
            else:
                self.logger.warning(f"缓存清空失败: {cache_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"清空缓存失败: {cache_name}, 错误: {str(e)}")
            return False

    def clear_all_caches(self) -> Dict[str, bool]:
        """
        清空所有缓存

        Returns:
            Dict[str, bool]: 每个缓存的清空结果
        """
        try:
            from .factory import _cache_instances
            
            results = {}
            for name in list(_cache_instances.keys()):
                results[name] = self.clear_cache(name)
            
            return results
            
        except Exception as e:
            self.logger.error(f"清空所有缓存失败: {str(e)}")
            return {}

    def cleanup_expired_caches(self) -> Dict[str, int]:
        """
        清理所有缓存的过期数据

        Returns:
            Dict[str, int]: 每个缓存清理的数量
        """
        try:
            from .factory import _cache_instances
            
            results = {}
            for name, cache in _cache_instances.items():
                try:
                    cleaned_count = cache.cleanup_expired()
                    results[name] = cleaned_count
                    self.logger.info(f"缓存 {name} 清理了 {cleaned_count} 个过期项")
                except Exception as e:
                    self.logger.error(f"清理缓存 {name} 失败: {str(e)}")
                    results[name] = -1
            
            return results
            
        except Exception as e:
            self.logger.error(f"清理过期缓存失败: {str(e)}")
            return {}

    def migrate_cache(self, source_name: str, target_name: str, 
                     source_type: str, target_type: str) -> bool:
        """
        迁移缓存数据

        Args:
            source_name: 源缓存名称
            target_name: 目标缓存名称
            source_type: 源缓存类型
            target_type: 目标缓存类型

        Returns:
            bool: 是否成功
        """
        try:
            # 创建源和目标缓存
            source_cache = get_cache(source_name, cache_type=source_type)
            target_cache = get_cache(target_name, cache_type=target_type)
            
            # 对于文件缓存，我们可以遍历所有文件
            if source_type == "file":
                migrated_count = self._migrate_from_file_cache(source_cache, target_cache)
            else:
                self.logger.warning(f"不支持从 {source_type} 类型缓存迁移")
                return False
            
            self.logger.info(f"缓存迁移完成: {source_name} -> {target_name}, 迁移了 {migrated_count} 个项")
            return True
            
        except Exception as e:
            self.logger.error(f"缓存迁移失败: {str(e)}")
            return False

    def _migrate_from_file_cache(self, source_cache, target_cache) -> int:
        """
        从文件缓存迁移数据

        Args:
            source_cache: 源缓存
            target_cache: 目标缓存

        Returns:
            int: 迁移的项数
        """
        migrated_count = 0
        
        try:
            # 遍历源缓存目录中的所有文件
            for cache_file in source_cache.cache_dir.glob("*.json"):
                try:
                    # 读取缓存文件
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        import json
                        cache_data = json.load(f)
                    
                    # 检查是否过期
                    if not source_cache._is_expired(cache_data):
                        # 计算剩余TTL
                        import time
                        remaining_ttl = int(cache_data["expires_at"] - time.time())
                        
                        # 从文件名反推原始键（这里简化处理）
                        key = cache_file.stem
                        
                        # 迁移到目标缓存
                        success = target_cache.set(key, cache_data["data"], ttl=remaining_ttl)
                        if success:
                            migrated_count += 1
                        
                except Exception as e:
                    self.logger.warning(f"迁移文件 {cache_file} 失败: {str(e)}")
                    continue
            
        except Exception as e:
            self.logger.error(f"遍历源缓存失败: {str(e)}")
        
        return migrated_count

    def test_cache_performance(self, cache_name: str, 
                             operations: int = 1000) -> Dict[str, float]:
        """
        测试缓存性能

        Args:
            cache_name: 缓存名称
            operations: 操作次数

        Returns:
            Dict[str, float]: 性能测试结果
        """
        try:
            import time
            cache = get_shared_cache(cache_name)
            
            # 测试写入性能
            start_time = time.time()
            for i in range(operations):
                cache.set(f"perf_test_{i}", f"value_{i}")
            write_time = time.time() - start_time
            
            # 测试读取性能
            start_time = time.time()
            for i in range(operations):
                cache.get(f"perf_test_{i}")
            read_time = time.time() - start_time
            
            # 清理测试数据
            for i in range(operations):
                cache.delete(f"perf_test_{i}")
            
            results = {
                "operations": operations,
                "write_time": write_time,
                "read_time": read_time,
                "write_ops_per_sec": operations / write_time if write_time > 0 else 0,
                "read_ops_per_sec": operations / read_time if read_time > 0 else 0
            }
            
            self.logger.info(f"缓存性能测试完成: {cache_name}, 结果: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"缓存性能测试失败: {cache_name}, 错误: {str(e)}")
            return {"error": str(e)}

    def health_check(self) -> Dict[str, Any]:
        """
        缓存健康检查

        Returns:
            Dict[str, Any]: 健康检查结果
        """
        try:
            from .factory import _cache_instances
            
            health_status = {
                "overall_status": "healthy",
                "total_instances": len(_cache_instances),
                "healthy_instances": 0,
                "unhealthy_instances": 0,
                "instances": {}
            }
            
            for name, cache in _cache_instances.items():
                try:
                    # 简单的读写测试
                    test_key = f"health_check_{name}"
                    test_value = "health_check_value"
                    
                    # 写入测试
                    write_success = cache.set(test_key, test_value, ttl=60)
                    
                    # 读取测试
                    read_value = cache.get(test_key)
                    read_success = read_value == test_value
                    
                    # 删除测试数据
                    cache.delete(test_key)
                    
                    if write_success and read_success:
                        health_status["instances"][name] = {
                            "status": "healthy",
                            "type": getattr(cache, '__class__', {}).get('__name__', 'unknown')
                        }
                        health_status["healthy_instances"] += 1
                    else:
                        health_status["instances"][name] = {
                            "status": "unhealthy",
                            "error": "读写测试失败"
                        }
                        health_status["unhealthy_instances"] += 1
                        
                except Exception as e:
                    health_status["instances"][name] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
                    health_status["unhealthy_instances"] += 1
            
            # 更新整体状态
            if health_status["unhealthy_instances"] > 0:
                health_status["overall_status"] = "degraded"
            
            if health_status["healthy_instances"] == 0:
                health_status["overall_status"] = "unhealthy"
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {str(e)}")
            return {
                "overall_status": "error",
                "error": str(e)
            }


# 全局缓存管理器实例
cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """
    获取缓存管理器实例

    Returns:
        CacheManager: 缓存管理器
    """
    return cache_manager 