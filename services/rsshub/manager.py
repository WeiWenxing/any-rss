"""
RSSHub管理器模块

该模块完全复用douyin模块的管理逻辑和数据结构，为RSSHub订阅提供统一的管理功能。
支持订阅管理、消息映射、已知内容去重等核心功能。

主要功能：
1. 完全复用douyin模块的数据结构（Subscription、MessageMapping等）
2. RSS订阅的增删改查管理
3. 消息ID映射的存储和查询
4. 已知RSS条目的去重管理
5. 多频道转发的支持
6. 历史对齐的数据接口

作者: Assistant
创建时间: 2024年
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from pathlib import Path

from .rss_entry import RSSEntry


class RSSHubManager:
    """
    RSSHub管理器

    完全复用douyin模块的管理逻辑，为RSS订阅提供统一的数据管理功能
    """

    def __init__(self, data_dir: str = "data/rsshub"):
        """
        初始化RSSHub管理器

        Args:
            data_dir: 数据存储目录
        """
        self.logger = logging.getLogger(__name__)
        self.data_dir = Path(data_dir)

        # 确保数据目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 数据文件路径（完全复用douyin模块的文件结构）
        self.config_dir = self.data_dir / "config"
        self.data_storage_dir = self.data_dir / "data"
        self.media_dir = self.data_dir / "media"
        
        self.subscriptions_file = self.config_dir / "subscriptions.json"
        self.message_mappings_file = self.config_dir / "message_mappings.json"

        # 确保目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_storage_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

        # 内存缓存（完全复用douyin模块的缓存结构）
        self._subscriptions_cache = {}
        self._message_mappings_cache = {}
        self._known_items_cache = {}

        # 加载数据
        self._load_all_data()

        self.logger.info(f"RSSHub管理器初始化完成，数据目录: {data_dir}")

    def _load_all_data(self):
        """加载所有数据到内存缓存"""
        try:
            self._load_subscriptions()
            self._load_message_mappings()
            self.logger.info("RSSHub数据加载完成")
        except Exception as e:
            self.logger.error(f"加载RSSHub数据失败: {str(e)}", exc_info=True)

    def _load_subscriptions(self):
        """加载订阅数据"""
        try:
            if self.subscriptions_file.exists():
                with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                    self._subscriptions_cache = json.load(f)
                self.logger.debug(f"加载订阅数据: {len(self._subscriptions_cache)} 个RSS源")
            else:
                self._subscriptions_cache = {}
                self.logger.debug("订阅文件不存在，初始化为空")
        except Exception as e:
            self.logger.error(f"加载订阅数据失败: {str(e)}", exc_info=True)
            self._subscriptions_cache = {}

    def _load_message_mappings(self):
        """加载消息映射数据"""
        try:
            if self.message_mappings_file.exists():
                with open(self.message_mappings_file, 'r', encoding='utf-8') as f:
                    self._message_mappings_cache = json.load(f)
                self.logger.debug(f"加载消息映射数据: {len(self._message_mappings_cache)} 个RSS源")
            else:
                self._message_mappings_cache = {}
                self.logger.debug("消息映射文件不存在，初始化为空")
        except Exception as e:
            self.logger.error(f"加载消息映射数据失败: {str(e)}", exc_info=True)
            self._message_mappings_cache = {}

    def _save_subscriptions(self):
        """保存订阅数据"""
        try:
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(self._subscriptions_cache, f, ensure_ascii=False, indent=2)
            self.logger.debug("订阅数据保存成功")
        except Exception as e:
            self.logger.error(f"保存订阅数据失败: {str(e)}", exc_info=True)

    def _save_message_mappings(self):
        """保存消息映射数据"""
        try:
            with open(self.message_mappings_file, 'w', encoding='utf-8') as f:
                json.dump(self._message_mappings_cache, f, ensure_ascii=False, indent=2)
            self.logger.debug("消息映射数据保存成功")
        except Exception as e:
            self.logger.error(f"保存消息映射数据失败: {str(e)}", exc_info=True)

    # ==================== 订阅管理接口 ====================

    def add_subscription(self, rss_url: str, chat_id: str, rss_title: str = "") -> bool:
        """
        添加RSS订阅（完全复用douyin模块的订阅结构）

        Args:
            rss_url: RSS源URL
            chat_id: 频道ID
            rss_title: RSS源标题（可选，仅用于日志）

        Returns:
            bool: 是否添加成功
        """
        try:
            # 初始化RSS源数据结构（完全复用douyin的简单映射格式）
            if rss_url not in self._subscriptions_cache:
                self._subscriptions_cache[rss_url] = []

            # 检查频道是否已存在
            channels = self._subscriptions_cache[rss_url]
            if chat_id not in channels:
                channels.append(chat_id)
                self._save_subscriptions()
                self.logger.info(f"添加RSS订阅成功: {rss_url} -> {chat_id}")
                return True
            else:
                self.logger.info(f"RSS订阅已存在: {rss_url} -> {chat_id}")
                return True

        except Exception as e:
            self.logger.error(f"添加RSS订阅失败: {rss_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False

    def remove_subscription(self, rss_url: str, chat_id: str) -> bool:
        """
        删除RSS订阅

        Args:
            rss_url: RSS源URL
            chat_id: 频道ID

        Returns:
            bool: 是否删除成功
        """
        try:
            if rss_url not in self._subscriptions_cache:
                self.logger.warning(f"RSS源不存在: {rss_url}")
                return False

            channels = self._subscriptions_cache[rss_url]
            if chat_id in channels:
                channels.remove(chat_id)

                # 如果没有频道订阅了，删除整个RSS源
                if not channels:
                    del self._subscriptions_cache[rss_url]
                    self.logger.info(f"删除RSS源（无订阅频道）: {rss_url}")

                self._save_subscriptions()
                self.logger.info(f"删除RSS订阅成功: {rss_url} -> {chat_id}")
                return True
            else:
                self.logger.warning(f"RSS订阅不存在: {rss_url} -> {chat_id}")
                return False

        except Exception as e:
            self.logger.error(f"删除RSS订阅失败: {rss_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False

    def get_subscription_channels(self, rss_url: str) -> List[str]:
        """
        获取RSS源的订阅频道列表

        Args:
            rss_url: RSS源URL

        Returns:
            List[str]: 订阅频道ID列表
        """
        if rss_url in self._subscriptions_cache:
            return self._subscriptions_cache[rss_url].copy()
        return []

    def get_all_rss_urls(self) -> List[str]:
        """
        获取所有RSS源URL列表

        Returns:
            List[str]: RSS源URL列表
        """
        return list(self._subscriptions_cache.keys())

    def get_channel_subscriptions(self, chat_id: str) -> List[str]:
        """
        获取频道的所有RSS订阅

        Args:
            chat_id: 频道ID

        Returns:
            List[str]: RSS源URL列表
        """
        subscriptions = []
        for rss_url, channels in self._subscriptions_cache.items():
            if chat_id in channels:
                subscriptions.append(rss_url)
        return subscriptions

    # ==================== 消息映射接口（完全复用douyin逻辑）====================

    def save_message_mapping(self, rss_url: str, item_id: str, chat_id: str, message_ids: List[int]):
        """
        保存消息ID映射（完全复用douyin模块的MessageMapping结构）

        Args:
            rss_url: RSS源URL
            item_id: RSS条目ID
            chat_id: 频道ID
            message_ids: 消息ID列表
        """
        try:
            # 初始化RSS源的消息映射
            if rss_url not in self._message_mappings_cache:
                self._message_mappings_cache[rss_url] = {}

            # 初始化条目的消息映射
            if item_id not in self._message_mappings_cache[rss_url]:
                self._message_mappings_cache[rss_url][item_id] = {}

            # 保存频道的消息ID列表
            self._message_mappings_cache[rss_url][item_id][chat_id] = message_ids

            self._save_message_mappings()
            self.logger.debug(f"保存消息映射: {rss_url}/{item_id} -> {chat_id}: {message_ids}")

        except Exception as e:
            self.logger.error(f"保存消息映射失败: {str(e)}", exc_info=True)

    def get_message_mapping(self, rss_url: str, item_id: str) -> Dict[str, List[int]]:
        """
        获取消息ID映射

        Args:
            rss_url: RSS源URL
            item_id: RSS条目ID

        Returns:
            Dict[str, List[int]]: 频道ID到消息ID列表的映射
        """
        try:
            if rss_url in self._message_mappings_cache:
                if item_id in self._message_mappings_cache[rss_url]:
                    return self._message_mappings_cache[rss_url][item_id].copy()
            return {}
        except Exception as e:
            self.logger.error(f"获取消息映射失败: {str(e)}", exc_info=True)
            return {}

    def get_all_available_message_sources(self, rss_url: str, item_id: str) -> List[Tuple[str, List[int]]]:
        """
        获取所有可用的消息转发源（完全复用douyin模块逻辑）

        这个方法是统一对齐器要求的接口，必须实现

        Args:
            rss_url: RSS源URL
            item_id: RSS条目ID

        Returns:
            List[Tuple[str, List[int]]]: 所有可用的转发源列表 [(频道ID, 消息ID列表), ...]
        """
        try:
            message_mapping = self.get_message_mapping(rss_url, item_id)
            available_sources = []

            for chat_id, message_ids in message_mapping.items():
                if message_ids:  # 只返回有消息ID的频道
                    available_sources.append((chat_id, message_ids))

            self.logger.debug(f"获取到 {len(available_sources)} 个可用转发源: {item_id}")
            return available_sources

        except Exception as e:
            self.logger.error(f"获取可用转发源失败: {str(e)}", exc_info=True)
            return []

    # ==================== 已知内容管理接口（复用douyin逻辑）====================

    def get_known_item_ids(self, rss_url: str) -> List[str]:
        """
        获取已知的RSS条目ID列表

        Args:
            rss_url: RSS源URL

        Returns:
            List[str]: 已知条目ID列表
        """
        try:
            # 检查缓存
            if rss_url in self._known_items_cache:
                return self._known_items_cache[rss_url].copy()

            # 从文件加载（按设计文档的目录结构）
            url_hash = self._safe_filename(rss_url)
            url_dir = self.data_storage_dir / url_hash
            known_items_file = url_dir / "known_item_ids.json"
            
            if known_items_file.exists():
                with open(known_items_file, 'r', encoding='utf-8') as f:
                    known_items = json.load(f)
                    self._known_items_cache[rss_url] = known_items
                    return known_items.copy()

            # 文件不存在，返回空列表
            self._known_items_cache[rss_url] = []
            return []

        except Exception as e:
            self.logger.error(f"获取已知条目ID失败: {rss_url}, 错误: {str(e)}", exc_info=True)
            return []

    def save_known_item_ids(self, rss_url: str, item_ids: List[str]):
        """
        保存已知的RSS条目ID列表

        Args:
            rss_url: RSS源URL
            item_ids: 条目ID列表
        """
        try:
            # 更新缓存
            self._known_items_cache[rss_url] = item_ids.copy()

            # 保存到文件（按设计文档的目录结构）
            url_hash = self._safe_filename(rss_url)
            url_dir = self.data_storage_dir / url_hash
            url_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存URL记录文件
            url_file = url_dir / "url.txt"
            with open(url_file, 'w', encoding='utf-8') as f:
                f.write(rss_url)
            
            # 保存已知条目ID文件
            known_items_file = url_dir / "known_item_ids.json"
            with open(known_items_file, 'w', encoding='utf-8') as f:
                json.dump(item_ids, f, ensure_ascii=False, indent=2)

            self.logger.debug(f"保存已知条目ID: {rss_url}, {len(item_ids)} 个")

        except Exception as e:
            self.logger.error(f"保存已知条目ID失败: {rss_url}, 错误: {str(e)}", exc_info=True)

    def add_known_item_id(self, rss_url: str, item_id: str):
        """
        添加单个已知条目ID

        Args:
            rss_url: RSS源URL
            item_id: 条目ID
        """
        try:
            known_items = self.get_known_item_ids(rss_url)
            if item_id not in known_items:
                known_items.append(item_id)
                self.save_known_item_ids(rss_url, known_items)
                self.logger.debug(f"添加已知条目ID: {rss_url}/{item_id}")
        except Exception as e:
            self.logger.error(f"添加已知条目ID失败: {str(e)}", exc_info=True)

    def is_known_item(self, rss_url: str, item_id: str) -> bool:
        """
        检查条目是否已知

        Args:
            rss_url: RSS源URL
            item_id: 条目ID

        Returns:
            bool: 是否已知
        """
        known_items = self.get_known_item_ids(rss_url)
        return item_id in known_items

    # ==================== 工具方法 ====================

    def _safe_filename(self, url: str) -> str:
        """
        将URL转换为安全的文件名

        Args:
            url: URL字符串

        Returns:
            str: 安全的文件名
        """
        import hashlib
        import re

        # 移除协议和特殊字符
        safe_name = re.sub(r'[^\w\-_.]', '_', url.replace('https://', '').replace('http://', ''))

        # 如果文件名太长，使用hash
        if len(safe_name) > 100:
            hash_obj = hashlib.md5(url.encode('utf-8'))
            safe_name = f"rss_{hash_obj.hexdigest()}"

        return safe_name

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取管理器统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            total_rss_sources = len(self._subscriptions_cache)
            total_channels = set()
            total_subscriptions = 0

            for channels in self._subscriptions_cache.values():
                total_subscriptions += len(channels)
                total_channels.update(channels)

            total_known_items = 0
            for rss_url in self._subscriptions_cache.keys():
                known_items = self.get_known_item_ids(rss_url)
                total_known_items += len(known_items)

            return {
                "total_rss_sources": total_rss_sources,
                "total_channels": len(total_channels),
                "total_subscriptions": total_subscriptions,
                "total_known_items": total_known_items,
                "data_dir": str(self.data_dir)
            }

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}", exc_info=True)
            return {}

    def cleanup_orphaned_data(self) -> int:
        """
        清理孤立的数据（没有订阅的RSS源数据）

        Returns:
            int: 清理的数据项数量
        """
        try:
            cleaned_count = 0
            active_rss_urls = set(self._subscriptions_cache.keys())

            # 清理消息映射中的孤立数据
            orphaned_mappings = []
            for rss_url in self._message_mappings_cache.keys():
                if rss_url not in active_rss_urls:
                    orphaned_mappings.append(rss_url)

            for rss_url in orphaned_mappings:
                del self._message_mappings_cache[rss_url]
                cleaned_count += 1

            if orphaned_mappings:
                self._save_message_mappings()
                self.logger.info(f"清理孤立消息映射: {len(orphaned_mappings)} 个")

            # 清理已知条目目录
            for url_dir in self.data_storage_dir.iterdir():
                if url_dir.is_dir():
                    # 从目录名反推RSS URL（简化处理）
                    dir_name = url_dir.name
                    found_match = False

                    for rss_url in active_rss_urls:
                        if self._safe_filename(rss_url) == dir_name:
                            found_match = True
                            break

                    if not found_match:
                        # 删除整个目录
                        import shutil
                        shutil.rmtree(url_dir)
                        cleaned_count += 1
                        self.logger.debug(f"删除孤立已知条目目录: {url_dir}")

            self.logger.info(f"数据清理完成，清理了 {cleaned_count} 个孤立数据项")
            return cleaned_count

        except Exception as e:
            self.logger.error(f"数据清理失败: {str(e)}", exc_info=True)
            return 0


# 便捷函数：创建RSSHub管理器实例
def create_rsshub_manager(data_dir: str = "data/rsshub") -> RSSHubManager:
    """
    创建RSSHub管理器实例

    Args:
        data_dir: 数据存储目录

    Returns:
        RSSHubManager: RSSHub管理器实例
    """
    return RSSHubManager(data_dir)


if __name__ == "__main__":
    # 模块测试代码
    def test_rsshub_manager():
        """测试RSSHub管理器功能"""
        print("🧪 RSSHub管理器模块测试")

        # 创建管理器
        manager = create_rsshub_manager("test_data/rsshub")
        print(f"✅ 创建RSSHub管理器: {type(manager).__name__}")

        # 测试添加订阅
        test_rss_url = "https://example.com/rss.xml"
        test_chat_id = "@test_channel"

        success = manager.add_subscription(test_rss_url, test_chat_id, "测试RSS源")
        print(f"✅ 添加订阅: {success}")

        # 测试获取订阅
        channels = manager.get_subscription_channels(test_rss_url)
        print(f"✅ 获取订阅频道: {len(channels)} 个")

        # 测试已知条目管理
        test_item_id = "test_item_123"
        manager.add_known_item_id(test_rss_url, test_item_id)
        is_known = manager.is_known_item(test_rss_url, test_item_id)
        print(f"✅ 已知条目管理: {is_known}")

        # 测试消息映射
        manager.save_message_mapping(test_rss_url, test_item_id, test_chat_id, [123, 124])
        mapping = manager.get_message_mapping(test_rss_url, test_item_id)
        print(f"✅ 消息映射: {len(mapping)} 个频道")

        # 测试统计信息
        stats = manager.get_statistics()
        print(f"✅ 统计信息: {stats['total_rss_sources']} 个RSS源")

        print("🎉 RSSHub管理器模块测试完成")

    # 运行测试
    test_rsshub_manager()