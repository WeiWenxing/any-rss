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
from .rss_parser import RSSParser, create_rss_parser
from services.common.unified_manager import UnifiedContentManager


class RSSHubManager(UnifiedContentManager):
    """
    RSSHub管理器

    继承统一管理器基类，完全复用douyin模块的管理逻辑，为RSS订阅提供统一的数据管理功能
    """

    def __init__(self, data_dir: str = "data/rsshub"):
        """
        初始化RSSHub管理器

        Args:
            data_dir: 数据存储目录
        """
        # 调用父类构造函数
        super().__init__(module_name="rsshub", data_dir=data_dir)

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

        # 初始化RSS解析器
        self.rss_parser = create_rss_parser()

        # 初始化并注册RSS转换器（确保转换器可用）
        from .rss_converter import create_rss_converter
        self.rss_converter = create_rss_converter()

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

    # ==================== 实现UnifiedContentManager抽象接口 ====================

    def get_subscriptions(self) -> Dict[str, List[str]]:
        """
        获取所有订阅信息

        Returns:
            Dict[str, List[str]]: {源URL: [频道ID列表]}
        """
        return self._subscriptions_cache.copy()

    def get_subscription_channels(self, source_url: str) -> List[str]:
        """
        获取指定源的订阅频道列表

        Args:
            source_url: 数据源URL

        Returns:
            List[str]: 频道ID列表
        """
        return self._subscriptions_cache.get(source_url, []).copy()

    def fetch_latest_content(self, source_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取指定源的最新内容

        Args:
            source_url: 数据源URL

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 内容数据列表)
        """
        try:
            self.logger.info(f"📥 开始获取RSS内容: {source_url}")

            # 使用RSS解析器获取最新内容
            entries = self.rss_parser.parse_feed(source_url)

            if not entries:
                self.logger.warning(f"📭 RSS源无内容或解析失败: {source_url}")
                return False, "RSS源无内容或解析失败", None

            self.logger.info(f"📊 RSS解析成功: 获取到 {len(entries)} 个条目")

            # 转换为统一的内容数据格式
            content_data_list = []
            for i, entry in enumerate(entries):
                try:
                    content_data = {
                        "title": entry.title,
                        "description": entry.description,
                        "link": entry.link,
                        "published": entry.published,
                        "updated": entry.updated,
                        "author": entry.author,
                        "item_id": entry.item_id,
                        "time": entry.effective_published_time.isoformat() if entry.effective_published_time else "",
                        "enclosures": [
                            {
                                "url": enc.url,
                                "type": enc.type,
                                "length": enc.length
                            } for enc in entry.enclosures
                        ] if entry.enclosures else []
                    }
                    content_data_list.append(content_data)

                    if i < 3:  # 只记录前3个条目的详细信息
                        self.logger.debug(f"📄 条目{i+1}: {entry.title[:50]}{'...' if len(entry.title) > 50 else ''} (ID: {entry.item_id})")

                except Exception as e:
                    self.logger.warning(f"⚠️ 转换条目{i+1}失败: {str(e)}")
                    continue

            self.logger.info(f"✅ 内容转换完成: 成功转换 {len(content_data_list)}/{len(entries)} 个条目")
            return True, "", content_data_list

        except Exception as e:
            self.logger.error(f"💥 获取RSS内容失败: {source_url}, 错误: {str(e)}", exc_info=True)
            return False, f"获取RSS内容失败: {str(e)}", None

    def get_known_item_ids(self, source_url: str) -> List[str]:
        """
        获取已知的内容ID列表

        Args:
            source_url: 数据源URL

        Returns:
            List[str]: 已知内容ID列表
        """
        try:
            # 检查缓存
            if source_url in self._known_items_cache:
                return self._known_items_cache[source_url].copy()

            # 从文件加载（按设计文档的目录结构）
            url_hash = self._safe_filename(source_url)
            url_dir = self.data_storage_dir / url_hash
            known_items_file = url_dir / "known_item_ids.json"

            if known_items_file.exists():
                with open(known_items_file, 'r', encoding='utf-8') as f:
                    known_items = json.load(f)
                    self._known_items_cache[source_url] = known_items
                    return known_items.copy()

            # 文件不存在，返回空列表
            self._known_items_cache[source_url] = []
            return []

        except Exception as e:
            self.logger.error(f"获取已知条目ID失败: {source_url}, 错误: {str(e)}", exc_info=True)
            return []

    def save_known_item_ids(self, source_url: str, item_ids: List[str]):
        """
        保存已知的内容ID列表

        Args:
            source_url: 数据源URL
            item_ids: 内容ID列表
        """
        try:
            # 更新缓存
            self._known_items_cache[source_url] = item_ids.copy()

            # 保存到文件
            url_hash = self._safe_filename(source_url)
            url_dir = self.data_storage_dir / url_hash
            url_dir.mkdir(parents=True, exist_ok=True)

            known_items_file = url_dir / "known_item_ids.json"
            with open(known_items_file, 'w', encoding='utf-8') as f:
                json.dump(item_ids, f, ensure_ascii=False, indent=2)

            self.logger.debug(f"保存已知条目ID成功: {source_url}, {len(item_ids)} 个")

        except Exception as e:
            self.logger.error(f"保存已知条目ID失败: {source_url}, 错误: {str(e)}", exc_info=True)

    def generate_content_id(self, content_data: Dict) -> str:
        """
        生成内容的唯一标识

        Args:
            content_data: 内容数据

        Returns:
            str: 唯一标识
        """
        # 如果内容数据中已有item_id，直接使用
        if "item_id" in content_data and content_data["item_id"]:
            return content_data["item_id"]

        # 否则根据内容生成ID（与RSS解析器的逻辑保持一致）
        if content_data.get("link"):
            return content_data["link"]
        elif content_data.get("title") and content_data.get("published"):
            return f"{content_data['title']}_{content_data['published']}"
        else:
            return f"rss_item_{hash(str(content_data))}"

    def save_message_mapping(self, source_url: str, item_id: str, chat_id: str, message_ids: List[int]):
        """
        保存消息ID映射

        Args:
            source_url: 数据源URL
            item_id: 内容ID
            chat_id: 频道ID
            message_ids: 消息ID列表
        """
        try:
            # 初始化数据结构
            if source_url not in self._message_mappings_cache:
                self._message_mappings_cache[source_url] = {}

            if item_id not in self._message_mappings_cache[source_url]:
                self._message_mappings_cache[source_url][item_id] = {}

            # 保存映射
            self._message_mappings_cache[source_url][item_id][chat_id] = message_ids

            # 保存到文件
            self._save_message_mappings()

            self.logger.debug(f"保存消息映射成功: {source_url}/{item_id} -> {chat_id}: {message_ids}")

        except Exception as e:
            self.logger.error(f"保存消息映射失败: {source_url}/{item_id} -> {chat_id}, 错误: {str(e)}", exc_info=True)

    def get_all_available_message_sources(self, source_url: str, item_id: str) -> List[Tuple[str, List[int]]]:
        """
        获取所有可用的消息转发源

        Args:
            source_url: 数据源URL
            item_id: 内容ID

        Returns:
            List[Tuple[str, List[int]]]: 所有可用的转发源列表 [(频道ID, 消息ID列表), ...]
        """
        try:
            if source_url not in self._message_mappings_cache:
                return []

            if item_id not in self._message_mappings_cache[source_url]:
                return []

            mappings = self._message_mappings_cache[source_url][item_id]
            return [(chat_id, msg_ids) for chat_id, msg_ids in mappings.items()]

        except Exception as e:
            self.logger.error(f"获取消息转发源失败: {source_url}/{item_id}, 错误: {str(e)}", exc_info=True)
            return []

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
            self.logger.info(f"💾 开始添加RSS订阅: {rss_url} -> {chat_id}")
            if rss_title:
                self.logger.info(f"📰 RSS源标题: {rss_title}")

            # 初始化RSS源数据结构（完全复用douyin的简单映射格式）
            if rss_url not in self._subscriptions_cache:
                self.logger.info(f"🆕 创建新的RSS源订阅: {rss_url}")
                self._subscriptions_cache[rss_url] = []

            # 检查频道是否已存在
            channels = self._subscriptions_cache[rss_url]
            if chat_id not in channels:
                channels.append(chat_id)
                self._save_subscriptions()
                self.logger.info(f"✅ 添加RSS订阅成功: {rss_url} -> {chat_id} (当前频道数: {len(channels)})")
                return True
            else:
                self.logger.info(f"ℹ️ RSS订阅已存在: {rss_url} -> {chat_id}")
                return True

        except Exception as e:
            self.logger.error(f"💥 添加RSS订阅失败: {rss_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
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
            self.logger.info(f"🗑️ 开始删除RSS订阅: {rss_url} -> {chat_id}")

            if rss_url not in self._subscriptions_cache:
                self.logger.warning(f"⚠️ RSS源不存在: {rss_url}")
                return False

            channels = self._subscriptions_cache[rss_url]
            if chat_id in channels:
                channels.remove(chat_id)

                # 如果没有频道订阅了，删除整个RSS源
                if not channels:
                    del self._subscriptions_cache[rss_url]
                    self.logger.info(f"🗑️ 删除RSS源（无订阅频道）: {rss_url}")
                else:
                    self.logger.info(f"📊 RSS源剩余频道数: {len(channels)}")

                self._save_subscriptions()
                self.logger.info(f"✅ 删除RSS订阅成功: {rss_url} -> {chat_id}")
                return True
            else:
                self.logger.warning(f"⚠️ RSS订阅不存在: {rss_url} -> {chat_id}")
                return False

        except Exception as e:
            self.logger.error(f"💥 删除RSS订阅失败: {rss_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False

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

    # ==================== 消息映射管理接口 ====================

    def get_message_mapping(self, rss_url: str, item_id: str) -> Dict[str, List[int]]:
        """
        获取指定RSS条目的消息映射

        Args:
            rss_url: RSS源URL
            item_id: RSS条目ID

        Returns:
            Dict[str, List[int]]: 消息映射 {频道ID: [消息ID列表]}
        """
        try:
            if rss_url in self._message_mappings_cache:
                if item_id in self._message_mappings_cache[rss_url]:
                    return self._message_mappings_cache[rss_url][item_id].copy()
            return {}
        except Exception as e:
            self.logger.error(f"获取消息映射失败: {rss_url}/{item_id}, 错误: {str(e)}", exc_info=True)
            return {}

    # ==================== 已知内容管理接口（复用douyin逻辑）====================

    def add_known_item_id(self, rss_url: str, item_id: str):
        """
        添加已知的RSS条目ID

        Args:
            rss_url: RSS源URL
            item_id: RSS条目ID
        """
        try:
            known_items = self.get_known_item_ids(rss_url)
            if item_id not in known_items:
                known_items.append(item_id)
                self.save_known_item_ids(rss_url, known_items)
                self.logger.debug(f"添加已知条目ID: {rss_url}/{item_id}")
        except Exception as e:
            self.logger.error(f"添加已知条目ID失败: {rss_url}/{item_id}, 错误: {str(e)}", exc_info=True)

    def is_known_item(self, rss_url: str, item_id: str) -> bool:
        """
        检查RSS条目是否已知

        Args:
            rss_url: RSS源URL
            item_id: RSS条目ID

        Returns:
            bool: 是否已知
        """
        try:
            known_items = self.get_known_item_ids(rss_url)
            return item_id in known_items
        except Exception as e:
            self.logger.error(f"检查已知条目失败: {rss_url}/{item_id}, 错误: {str(e)}", exc_info=True)
            return False

    def _safe_filename(self, url: str) -> str:
        """
        生成安全的文件名（复用douyin模块逻辑）

        Args:
            url: URL字符串

        Returns:
            str: 安全的文件名
        """
        import hashlib
        import re

        # 移除协议前缀
        clean_url = re.sub(r'^https?://', '', url)
        # 替换特殊字符
        clean_url = re.sub(r'[^\w\-_.]', '_', clean_url)
        # 限制长度并添加哈希
        if len(clean_url) > 50:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            clean_url = clean_url[:42] + '_' + url_hash

        return clean_url

    # ==================== 统计和维护接口 ====================

    def cleanup_orphaned_data(self) -> int:
        """
        清理孤立的数据（没有对应订阅的数据）

        Returns:
            int: 清理的数据项数量
        """
        try:
            cleaned_count = 0
            current_urls = set(self._subscriptions_cache.keys())

            # 清理消息映射中的孤立数据
            orphaned_urls = set(self._message_mappings_cache.keys()) - current_urls
            for url in orphaned_urls:
                del self._message_mappings_cache[url]
                cleaned_count += 1

            # 清理已知条目缓存中的孤立数据
            orphaned_cache_urls = set(self._known_items_cache.keys()) - current_urls
            for url in orphaned_cache_urls:
                del self._known_items_cache[url]
                cleaned_count += 1

            # 清理文件系统中的孤立目录
            if self.data_storage_dir.exists():
                for url_dir in self.data_storage_dir.iterdir():
                    if url_dir.is_dir():
                        # 尝试找到对应的URL
                        found = False
                        for url in current_urls:
                            if self._safe_filename(url) == url_dir.name:
                                found = True
                                break

                        if not found:
                            # 删除孤立目录
                            import shutil
                            shutil.rmtree(url_dir)
                            cleaned_count += 1

            if cleaned_count > 0:
                self._save_message_mappings()
                self.logger.info(f"清理孤立数据完成，清理了 {cleaned_count} 个数据项")

            return cleaned_count

        except Exception as e:
            self.logger.error(f"清理孤立数据失败: {str(e)}", exc_info=True)
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

        # 测试订阅管理
        test_url = "https://example.com/rss.xml"
        test_chat_id = "@test_channel"

        success = manager.add_subscription(test_url, test_chat_id)
        print(f"✅ 添加订阅: {success}")

        channels = manager.get_subscription_channels(test_url)
        print(f"✅ 获取订阅频道: {channels}")

        # 测试统计信息
        stats = manager.get_statistics()
        print(f"✅ 获取统计信息: {stats}")

        # 测试数据清理
        cleaned = manager.cleanup_orphaned_data()
        print(f"✅ 清理孤立数据: {cleaned} 个")

        print("🎉 RSSHub管理器模块测试完成")

    # 运行测试
    test_rsshub_manager()