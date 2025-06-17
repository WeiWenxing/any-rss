"""
统一业务管理器基类

该模块抽取了douyin模块的核心业务逻辑，为所有数据源模块提供统一的业务处理模式。
包含订阅管理、内容检查、批量发送、历史对齐等通用业务流程。

主要功能：
1. 抽象的订阅管理接口
2. 通用的内容更新检查流程
3. 统一的批量发送算法（多频道高效转发）
4. 标准的已发送标记逻辑
5. 可配置的间隔管理集成
6. 统一的错误处理和日志记录
7. 通用的数据存储和管理功能（文件系统、缓存、JSON读写）

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
import json
import hashlib
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple, Union
from pathlib import Path
from telegram import Bot, Message
from datetime import datetime

from .unified_interval_manager import UnifiedIntervalManager
from .unified_sender import UnifiedTelegramSender
from .telegram_message import TelegramMessage
from .message_converter import MessageConverter, get_converter, ConverterType


class UnifiedContentManager(ABC):
    """
    统一内容管理器基类

    抽取douyin模块的核心业务逻辑，为所有数据源模块提供统一的业务处理模式
    包含完整的数据存储和管理功能
    """

    def __init__(self, module_name: str, data_dir: str = None):
        """
        初始化统一管理器

        Args:
            module_name: 模块名称（如'douyin', 'rsshub'）
            data_dir: 数据存储目录（可选）
        """
        self.module_name = module_name
        self.logger = logging.getLogger(f"{module_name}_manager")

        # 初始化统一组件
        self.sender = UnifiedTelegramSender()
        self.interval_manager = UnifiedIntervalManager("batch_send")

        # 初始化数据存储（如果提供了data_dir）
        if data_dir:
            self._init_data_storage(data_dir)
        else:
            # 如果没有提供data_dir，子类需要自己管理数据存储
            self._subscriptions_cache = None
            self._message_mappings_cache = None
            self._known_items_cache = None

        self.logger.info(f"{module_name}统一管理器初始化完成")

    def _init_data_storage(self, data_dir: str):
        """
        初始化数据存储系统（通用实现）

        Args:
            data_dir: 数据存储目录
        """
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

        self.logger.info(f"数据存储系统初始化完成，数据目录: {data_dir}")

    def _load_all_data(self):
        """加载所有数据到内存缓存（通用实现）"""
        try:
            self._load_subscriptions()
            self._load_message_mappings()
            self.logger.info(f"{self.module_name}数据加载完成")
        except Exception as e:
            self.logger.error(f"加载{self.module_name}数据失败: {str(e)}", exc_info=True)

    def _load_subscriptions(self):
        """加载订阅数据（通用实现）"""
        try:
            if self.subscriptions_file.exists():
                with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                    self._subscriptions_cache = json.load(f)
                self.logger.debug(f"加载订阅数据: {len(self._subscriptions_cache)} 个源")
            else:
                self._subscriptions_cache = {}
                self.logger.debug("订阅文件不存在，初始化为空")
        except Exception as e:
            self.logger.error(f"加载订阅数据失败: {str(e)}", exc_info=True)
            self._subscriptions_cache = {}

    def _load_message_mappings(self):
        """加载消息映射数据（通用实现）"""
        try:
            if self.message_mappings_file.exists():
                with open(self.message_mappings_file, 'r', encoding='utf-8') as f:
                    self._message_mappings_cache = json.load(f)
                self.logger.debug(f"加载消息映射数据: {len(self._message_mappings_cache)} 个源")
            else:
                self._message_mappings_cache = {}
                self.logger.debug("消息映射文件不存在，初始化为空")
        except Exception as e:
            self.logger.error(f"加载消息映射数据失败: {str(e)}", exc_info=True)
            self._message_mappings_cache = {}

    def _save_subscriptions(self):
        """保存订阅数据（通用实现）"""
        try:
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(self._subscriptions_cache, f, ensure_ascii=False, indent=2)
            self.logger.debug("订阅数据保存成功")
        except Exception as e:
            self.logger.error(f"保存订阅数据失败: {str(e)}", exc_info=True)

    def _save_message_mappings(self):
        """保存消息映射数据（通用实现）"""
        try:
            with open(self.message_mappings_file, 'w', encoding='utf-8') as f:
                json.dump(self._message_mappings_cache, f, ensure_ascii=False, indent=2)
            self.logger.debug("消息映射数据保存成功")
        except Exception as e:
            self.logger.error(f"保存消息映射数据失败: {str(e)}", exc_info=True)

    def _safe_filename(self, url: str) -> str:
        """
        生成安全的文件名（通用实现，复用douyin模块逻辑）

        Args:
            url: URL字符串

        Returns:
            str: 安全的文件名
        """
        # 移除协议前缀
        clean_url = re.sub(r'^https?://', '', url)
        # 替换特殊字符
        clean_url = re.sub(r'[^\w\-_.]', '_', clean_url)
        # 限制长度并添加哈希
        if len(clean_url) > 50:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            clean_url = clean_url[:42] + '_' + url_hash

        return clean_url

    # ==================== 通用数据管理实现 ====================

    def get_subscriptions(self) -> Dict[str, List[str]]:
        """
        获取所有订阅信息（通用实现）

        Returns:
            Dict[str, List[str]]: {源URL: [频道ID列表]}
        """
        if self._subscriptions_cache is None:
            # 如果没有初始化数据存储，子类需要自己实现
            raise NotImplementedError("数据存储未初始化，子类需要实现此方法")
        return self._subscriptions_cache.copy()

    def get_subscription_channels(self, source_url: str) -> List[str]:
        """
        获取指定源的订阅频道列表（通用实现）

        Args:
            source_url: 数据源URL

        Returns:
            List[str]: 频道ID列表
        """
        if self._subscriptions_cache is None:
            raise NotImplementedError("数据存储未初始化，子类需要实现此方法")
        return self._subscriptions_cache.get(source_url, []).copy()

    def get_known_item_ids(self, source_url: str) -> List[str]:
        """
        获取已知的内容ID列表（通用实现）

        Args:
            source_url: 数据源URL

        Returns:
            List[str]: 已知内容ID列表
        """
        try:
            # 检查缓存
            if self._known_items_cache is not None and source_url in self._known_items_cache:
                return self._known_items_cache[source_url].copy()

            # 从文件加载（按设计文档的目录结构）
            url_hash = self._safe_filename(source_url)
            url_dir = self.data_storage_dir / url_hash
            known_items_file = url_dir / "known_item_ids.json"

            if known_items_file.exists():
                with open(known_items_file, 'r', encoding='utf-8') as f:
                    known_items = json.load(f)
                    if self._known_items_cache is not None:
                        self._known_items_cache[source_url] = known_items
                    return known_items.copy()

            # 文件不存在，返回空列表
            if self._known_items_cache is not None:
                self._known_items_cache[source_url] = []
            return []

        except Exception as e:
            self.logger.error(f"获取已知条目ID失败: {source_url}, 错误: {str(e)}", exc_info=True)
            return []

    def save_known_item_ids(self, source_url: str, item_ids: List[str]):
        """
        保存已知的内容ID列表（通用实现）

        Args:
            source_url: 数据源URL
            item_ids: 内容ID列表
        """
        try:
            # 更新缓存
            if self._known_items_cache is not None:
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

    def save_message_mapping(self, source_url: str, item_id: str, chat_id: str, message_ids: List[int]):
        """
        保存消息ID映射（通用实现）

        Args:
            source_url: 数据源URL
            item_id: 内容ID
            chat_id: 频道ID
            message_ids: 消息ID列表
        """
        try:
            if self._message_mappings_cache is None:
                raise NotImplementedError("数据存储未初始化，子类需要实现此方法")

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
        获取所有可用的消息转发源（通用实现）

        Args:
            source_url: 数据源URL
            item_id: 内容ID

        Returns:
            List[Tuple[str, List[int]]]: 所有可用的转发源列表 [(频道ID, 消息ID列表), ...]
        """
        try:
            if self._message_mappings_cache is None:
                raise NotImplementedError("数据存储未初始化，子类需要实现此方法")

            if source_url not in self._message_mappings_cache:
                return []

            if item_id not in self._message_mappings_cache[source_url]:
                return []

            mappings = self._message_mappings_cache[source_url][item_id]
            return [(chat_id, msg_ids) for chat_id, msg_ids in mappings.items()]

        except Exception as e:
            self.logger.error(f"获取消息转发源失败: {source_url}/{item_id}, 错误: {str(e)}", exc_info=True)
            return []

    # ==================== 通用订阅管理实现 ====================

    def add_subscription(self, source_url: str, chat_id: str, title: str = "") -> bool:
        """
        添加订阅（通用实现，完全复用douyin模块的订阅结构）

        Args:
            source_url: 数据源URL
            chat_id: 频道ID
            title: 源标题（可选，仅用于日志）

        Returns:
            bool: 是否添加成功
        """
        try:
            if self._subscriptions_cache is None:
                raise NotImplementedError("数据存储未初始化，子类需要实现此方法")

            self.logger.info(f"💾 开始添加{self.module_name}订阅: {source_url} -> {chat_id}")
            if title:
                self.logger.info(f"📰 源标题: {title}")

            # 初始化源数据结构（完全复用douyin的简单映射格式）
            if source_url not in self._subscriptions_cache:
                self.logger.info(f"🆕 创建新的{self.module_name}源订阅: {source_url}")
                self._subscriptions_cache[source_url] = []

            # 检查频道是否已存在
            channels = self._subscriptions_cache[source_url]
            if chat_id not in channels:
                channels.append(chat_id)
                self._save_subscriptions()
                self.logger.info(f"✅ 添加{self.module_name}订阅成功: {source_url} -> {chat_id} (当前频道数: {len(channels)})")
                return True
            else:
                self.logger.info(f"ℹ️ {self.module_name}订阅已存在: {source_url} -> {chat_id}")
                return True

        except Exception as e:
            self.logger.error(f"💥 添加{self.module_name}订阅失败: {source_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False

    def remove_subscription(self, source_url: str, chat_id: str) -> bool:
        """
        删除订阅（通用实现）

        Args:
            source_url: 数据源URL
            chat_id: 频道ID

        Returns:
            bool: 是否删除成功
        """
        try:
            if self._subscriptions_cache is None:
                raise NotImplementedError("数据存储未初始化，子类需要实现此方法")

            self.logger.info(f"🗑️ 开始删除{self.module_name}订阅: {source_url} -> {chat_id}")

            if source_url not in self._subscriptions_cache:
                self.logger.warning(f"⚠️ {self.module_name}源不存在: {source_url}")
                return False

            channels = self._subscriptions_cache[source_url]
            if chat_id in channels:
                channels.remove(chat_id)

                # 如果没有频道订阅了，删除整个源
                if not channels:
                    del self._subscriptions_cache[source_url]
                    self.logger.info(f"🗑️ 删除{self.module_name}源（无订阅频道）: {source_url}")
                else:
                    self.logger.info(f"📊 {self.module_name}源剩余频道数: {len(channels)}")

                self._save_subscriptions()
                self.logger.info(f"✅ 删除{self.module_name}订阅成功: {source_url} -> {chat_id}")
                return True
            else:
                self.logger.warning(f"⚠️ {self.module_name}订阅不存在: {source_url} -> {chat_id}")
                return False

        except Exception as e:
            self.logger.error(f"💥 删除{self.module_name}订阅失败: {source_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False

    # ==================== 通用已知内容管理实现 ====================

    def add_known_item_id(self, source_url: str, item_id: str):
        """
        添加已知的内容ID（通用实现）

        Args:
            source_url: 数据源URL
            item_id: 内容ID
        """
        try:
            known_items = self.get_known_item_ids(source_url)
            if item_id not in known_items:
                known_items.append(item_id)
                self.save_known_item_ids(source_url, known_items)
                self.logger.debug(f"添加已知条目ID: {source_url}/{item_id}")
        except Exception as e:
            self.logger.error(f"添加已知条目ID失败: {source_url}/{item_id}, 错误: {str(e)}", exc_info=True)

    def is_known_item(self, source_url: str, item_id: str) -> bool:
        """
        检查内容是否已知（通用实现）

        Args:
            source_url: 数据源URL
            item_id: 内容ID

        Returns:
            bool: 是否已知
        """
        try:
            known_items = self.get_known_item_ids(source_url)
            return item_id in known_items
        except Exception as e:
            self.logger.error(f"检查已知条目失败: {source_url}/{item_id}, 错误: {str(e)}", exc_info=True)
            return False

    # ==================== 通用便利方法 ====================

    def get_channel_subscriptions(self, chat_id: str) -> List[str]:
        """
        获取频道的所有订阅（通用实现）

        Args:
            chat_id: 频道ID

        Returns:
            List[str]: 数据源URL列表
        """
        subscriptions = []
        for source_url, channels in self.get_subscriptions().items():
            if chat_id in channels:
                subscriptions.append(source_url)
        return subscriptions

    def get_message_mapping(self, source_url: str, item_id: str) -> Dict[str, List[int]]:
        """
        获取指定条目的消息映射（通用实现）

        Args:
            source_url: 数据源URL
            item_id: 内容ID

        Returns:
            Dict[str, List[int]]: 消息映射 {频道ID: [消息ID列表]}
        """
        try:
            sources = self.get_all_available_message_sources(source_url, item_id)
            return {chat_id: msg_ids for chat_id, msg_ids in sources}
        except Exception as e:
            self.logger.error(f"获取消息映射失败: {source_url}/{item_id}, 错误: {str(e)}", exc_info=True)
            return {}

    def get_all_source_urls(self) -> List[str]:
        """
        获取所有数据源URL列表（通用实现）

        Returns:
            List[str]: 数据源URL列表
        """
        return list(self.get_subscriptions().keys())

    def cleanup_orphaned_data(self) -> int:
        """
        清理孤立的数据（没有对应订阅的数据）（通用实现）

        Returns:
            int: 清理的文件数量
        """
        try:
            self.logger.info(f"🧹 开始清理{self.module_name}孤立数据")

            # 获取当前所有订阅的URL
            current_urls = set(self.get_subscriptions().keys())

            # 扫描data目录
            cleaned_count = 0
            if hasattr(self, 'data_storage_dir') and self.data_storage_dir.exists():
                for url_dir in self.data_storage_dir.iterdir():
                    if url_dir.is_dir():
                        # 检查是否有对应的URL文件
                        url_file = url_dir / "url.txt"
                        if url_file.exists():
                            try:
                                stored_url = url_file.read_text(encoding='utf-8').strip()
                                if stored_url not in current_urls:
                                    # 删除孤立的目录
                                    import shutil
                                    shutil.rmtree(url_dir)
                                    cleaned_count += 1
                                    self.logger.info(f"🗑️ 删除孤立数据目录: {url_dir.name} (URL: {stored_url})")
                            except Exception as e:
                                self.logger.warning(f"⚠️ 处理目录失败: {url_dir}, 错误: {str(e)}")
                        else:
                            # 没有URL文件的目录也删除
                            import shutil
                            shutil.rmtree(url_dir)
                            cleaned_count += 1
                            self.logger.info(f"🗑️ 删除无效数据目录: {url_dir.name}")

            self.logger.info(f"✅ {self.module_name}数据清理完成，清理了 {cleaned_count} 个孤立目录")
            return cleaned_count

        except Exception as e:
            self.logger.error(f"💥 清理{self.module_name}数据失败: {str(e)}", exc_info=True)
            return 0

    # ==================== 通用维护方法 ====================

    def cleanup_old_known_items(self, max_known_items: int = 10000) -> int:
        """
        清理过期的已知条目ID（保留最近的条目）（通用实现）

        Args:
            max_known_items: 每个源最多保留的已知条目数量

        Returns:
            int: 清理的条目总数
        """
        try:
            all_source_urls = self.get_all_source_urls()
            total_removed = 0

            for source_url in all_source_urls:
                try:
                    known_item_ids = self.get_known_item_ids(source_url)

                    if len(known_item_ids) > max_known_items:
                        # 保留最新的条目（简单的FIFO策略）
                        trimmed_ids = known_item_ids[-max_known_items:]
                        self.save_known_item_ids(source_url, trimmed_ids)

                        removed_count = len(known_item_ids) - len(trimmed_ids)
                        total_removed += removed_count
                        self.logger.info(f"清理{self.module_name}源过期条目: {source_url}, 移除 {removed_count} 个旧条目")

                except Exception as e:
                    self.logger.warning(f"清理{self.module_name}源已知条目失败: {source_url}, 错误: {str(e)}")
                    continue

            self.logger.info(f"✅ {self.module_name}已知条目清理完成，总共移除 {total_removed} 个过期条目")
            return total_removed

        except Exception as e:
            self.logger.error(f"清理{self.module_name}已知条目失败: {str(e)}", exc_info=True)
            return 0

    # ==================== 抽象接口（子类必须实现）====================

    @abstractmethod
    def fetch_latest_content(self, source_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取指定源的最新内容

        Args:
            source_url: 数据源URL

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 内容数据列表)
        """
        pass

    @abstractmethod
    def generate_content_id(self, content_data: Dict) -> str:
        """
        生成内容的唯一标识

        Args:
            content_data: 内容数据

        Returns:
            str: 唯一标识
        """
        pass

    @abstractmethod
    def _get_module_converter(self):
        """
        获取模块特定的消息转换器

        Returns:
            MessageConverter: 消息转换器实例
        """
        pass

    # ==================== 通用业务逻辑（完全复用douyin逻辑）====================

    def check_updates(self, source_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        检查指定数据源的更新（完全复用douyin模块逻辑）

        Args:
            source_url: 数据源URL

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 新内容数据列表)
        """
        try:
            self.logger.info(f"🔍 开始检查{self.module_name}更新: {source_url}")

            # 获取订阅信息
            subscriptions = self.get_subscriptions()
            if source_url not in subscriptions:
                self.logger.error(f"❌ 订阅不存在: {source_url}")
                return False, "订阅不存在", None

            # 获取订阅的频道列表
            subscribed_channels = subscriptions[source_url]
            if not subscribed_channels:
                self.logger.error(f"❌ 该URL没有订阅频道: {source_url}")
                return False, "该URL没有订阅频道", None

            self.logger.info(f"📊 订阅统计: {len(subscribed_channels)} 个频道订阅了此源")

            # 获取当前全部内容
            self.logger.info(f"📥 获取最新内容数据")
            success, error_msg, all_content_data = self.fetch_latest_content(source_url)
            if not success:
                self.logger.error(f"❌ 获取内容失败: {error_msg}")
                return False, error_msg, None

            if not all_content_data or len(all_content_data) == 0:
                self.logger.warning(f"📭 获取到的内容数据为空")
                return False, "获取到的内容数据为空", None

            self.logger.info(f"📊 获取到内容: {len(all_content_data)} 个条目")

            # 获取已知的item IDs（全局已发送的）
            self.logger.info(f"📋 获取已知内容ID列表")
            known_item_ids = self.get_known_item_ids(source_url)
            self.logger.info(f"📊 已知内容统计: {len(known_item_ids)} 个已发送条目")

            # 找出新的items
            new_items = []

            for i, content_data in enumerate(all_content_data):
                item_id = self.generate_content_id(content_data)

                # 如果这个item ID不在已知列表中，说明是新的
                if item_id not in known_item_ids:
                    # 添加item_id和频道信息到内容中，用于后续发送
                    content_data["item_id"] = item_id
                    content_data["target_channels"] = subscribed_channels.copy()
                    new_items.append(content_data)

                    if len(new_items) <= 3:  # 只记录前3个新内容的详细信息
                        self.logger.info(f"🆕 发现新内容{len(new_items)}: {content_data.get('title', '无标题')[:50]}{'...' if len(content_data.get('title', '')) > 50 else ''} (ID: {item_id}) -> 频道: {subscribed_channels}")
                    elif len(new_items) == 4:
                        self.logger.info(f"🆕 还有更多新内容...")

            if new_items:
                # 保存最新内容引用
                self._save_latest_content(source_url, all_content_data)

                self.logger.info(f"🎉 发现 {len(new_items)} 个新内容，将发送到 {len(subscribed_channels)} 个频道")
                return True, f"发现 {len(new_items)} 个新内容", new_items
            else:
                self.logger.info(f"📭 无新内容: {source_url}")
                return True, "无新内容", None

        except Exception as e:
            self.logger.error(f"💥 检查{self.module_name}更新失败: {source_url}", exc_info=True)
            return False, f"检查失败: {str(e)}", None

    def mark_item_as_sent(self, source_url: str, content_data: Dict) -> bool:
        """
        标记某个item为已成功发送（完全复用douyin模块逻辑）

        Args:
            source_url: 数据源URL
            content_data: 内容数据

        Returns:
            bool: 是否标记成功
        """
        try:
            item_id = self.generate_content_id(content_data)
            known_item_ids = self.get_known_item_ids(source_url)

            # 如果不在已知列表中，添加进去
            if item_id not in known_item_ids:
                known_item_ids.append(item_id)
                self.save_known_item_ids(source_url, known_item_ids)
                self.logger.info(f"标记item为已发送: {content_data.get('title', '无标题')} (ID: {item_id})")
                return True
            else:
                self.logger.debug(f"item已在已知列表中: {item_id}")
                return True

        except Exception as e:
            self.logger.error(f"标记item为已发送失败: {source_url}, 错误: {str(e)}", exc_info=True)
            return False

    async def send_content_batch(self, bot: Bot, content_items: List[Dict], source_url: str, target_channels: List[str]) -> int:
        """
        批量发送内容到多个频道（完全复用douyin的多频道高效转发算法）

        Args:
            bot: Telegram Bot实例
            content_items: 要发送的内容列表
            source_url: 数据源URL
            target_channels: 目标频道列表

        Returns:
            int: 成功发送的内容数量
        """
        self.logger.info(f"📤 开始批量发送 {len(content_items)} 个内容到 {len(target_channels)} 个频道")
        self.logger.info(f"📊 发送统计预估: 总操作数 = {len(content_items)} × {len(target_channels)} = {len(content_items) * len(target_channels)}")

        # 重新初始化间隔管理器为批量发送场景
        self.interval_manager = UnifiedIntervalManager("batch_send")
        sent_count = 0

        # 按时间排序（从旧到新）
        sorted_items = self._sort_content_by_time(content_items)
        self.logger.info(f"📅 内容按时间排序完成")

        for i, content in enumerate(sorted_items):
            # 为当前内容项维护成功记录（内存中）
            successful_channels = {}  # {channel_id: [message_id1, message_id2, ...]}

            try:
                self.logger.info(f"📝 处理内容 {i+1}/{len(sorted_items)}: {content.get('title', '无标题')[:50]}{'...' if len(content.get('title', '')) > 50 else ''}")

                # 发送前等待（使用配置化间隔管理器）
                await self.interval_manager.wait_before_send(
                    content_index=i,
                    total_content=len(sorted_items),
                    recent_error_rate=self.interval_manager.get_recent_error_rate()
                )

                # 确保content有item_id字段
                if 'item_id' not in content:
                    content['item_id'] = self.generate_content_id(content)
                    self.logger.warning(f"⚠️ 内容缺少item_id，动态生成: {content['item_id']}")

                # 步骤1：依次尝试每个频道作为发送频道，直到成功（容错设计）
                send_success = False

                # 依次尝试每个频道作为发送频道，直到成功
                for j, potential_send_channel in enumerate(target_channels):
                    try:
                        self.logger.info(f"📡 尝试发送到频道 {j+1}/{len(target_channels)} {potential_send_channel}: {content.get('title', '无标题')[:30]}{'...' if len(content.get('title', '')) > 30 else ''}")

                        # 转换为统一消息格式
                        converter = self._get_module_converter()
                        if not converter:
                            self.logger.error(f"❌ 无法获取转换器，跳过内容: {content.get('title', '无标题')}")
                            continue

                        telegram_message = converter.convert(content)

                        # 使用统一发送器发送
                        messages = await self.sender.send_message(bot, potential_send_channel, telegram_message)

                        if messages:
                            # 提取消息ID列表
                            message_ids = [msg.message_id for msg in messages]
                            self.save_message_mapping(source_url, content['item_id'], potential_send_channel, message_ids)
                            successful_channels[potential_send_channel] = message_ids  # 内存记录
                            self.logger.info(f"✅ 频道发送成功: {potential_send_channel}, 消息ID列表: {message_ids}")

                            send_success = True
                            # 更新统计信息（发送成功）
                            self.interval_manager.update_statistics(success=True)
                            break  # 成功后跳出循环
                    except Exception as send_error:
                        self.logger.warning(f"⚠️ 向 {potential_send_channel} 发送失败: {send_error}")
                        continue  # 尝试下一个频道

                # 如果所有频道发送都失败，跳过这个内容
                if not send_success:
                    self.logger.error(f"❌ 所有频道发送都失败，跳过内容: {content.get('title', '无标题')}")
                    # 更新统计信息（发送失败）
                    self.interval_manager.update_statistics(success=False)
                    continue

                # 步骤2：向剩余频道转发
                remaining_channels = [ch for ch in target_channels if ch not in successful_channels]
                if remaining_channels:
                    self.logger.info(f"🔄 开始转发到剩余 {len(remaining_channels)} 个频道")
                    # 初始化转发专用间隔管理器
                    forward_interval_manager = UnifiedIntervalManager("forward")

                    for channel_index, channel in enumerate(remaining_channels):
                        success = False

                        # 转发前等待（使用转发专用间隔管理器）
                        await forward_interval_manager.wait_before_send(
                            content_index=channel_index,
                            total_content=len(remaining_channels),
                            recent_error_rate=forward_interval_manager.get_recent_error_rate()
                        )

                        # 从所有成功频道中尝试转发（统一处理，不区分发送频道）
                        for source_channel, source_msg_ids in successful_channels.items():
                            if source_channel != channel:  # 不从自己转发给自己
                                try:
                                    self.logger.info(f"🔄 尝试转发: {source_channel} -> {channel}")
                                    forwarded_messages = await bot.copy_messages(
                                        chat_id=channel,
                                        from_chat_id=source_channel,
                                        message_ids=source_msg_ids
                                    )
                                    # 处理返回的消息（可能是单个消息、消息列表或消息元组）
                                    if isinstance(forwarded_messages, (list, tuple)):
                                        forwarded_ids = [msg.message_id for msg in forwarded_messages]
                                    else:
                                        forwarded_ids = [forwarded_messages.message_id]
                                    self.save_message_mapping(source_url, content['item_id'], channel, forwarded_ids)
                                    successful_channels[channel] = forwarded_ids  # 内存记录
                                    self.logger.info(f"✅ 转发成功: {source_channel} -> {channel}, 消息ID列表: {forwarded_ids}")
                                    # 更新转发统计信息（转发成功）
                                    forward_interval_manager.update_statistics(success=True)
                                    success = True
                                    break  # 转发成功，跳出循环
                                except Exception as forward_error:
                                    self.logger.debug(f"⚠️ 从 {source_channel} 转发到 {channel} 失败: {forward_error}")
                                    # 检查是否是Flood Control错误（使用转发专用间隔管理器）
                                    if "flood control" in str(forward_error).lower():
                                        await forward_interval_manager.wait_after_error("flood_control")
                                    elif "rate limit" in str(forward_error).lower():
                                        await forward_interval_manager.wait_after_error("rate_limit")
                                    else:
                                        await forward_interval_manager.wait_after_error("other")
                                    continue  # 转发失败，尝试下一个源频道

                        # 所有转发都失败，最后降级为直接发送
                        if not success:
                            self.logger.warning(f"⚠️ 所有转发都失败，降级发送: {channel}")
                            try:
                                # 转换为统一消息格式
                                converter = self._get_module_converter()
                                if not converter:
                                    self.logger.error(f"❌ 无法获取转换器，跳过降级发送: {channel}")
                                    continue

                                telegram_message = converter.convert(content)

                                # 使用统一发送器发送
                                fallback_messages = await self.sender.send_message(bot, channel, telegram_message)

                                if fallback_messages:
                                    fallback_ids = [msg.message_id for msg in fallback_messages]
                                    self.save_message_mapping(source_url, content['item_id'], channel, fallback_ids)
                                    successful_channels[channel] = fallback_ids  # 内存记录
                                    self.logger.info(f"✅ 降级发送成功: {channel}")
                                    # 更新转发统计信息（降级发送成功）
                                    forward_interval_manager.update_statistics(success=True)
                            except Exception as send_error:
                                self.logger.error(f"❌ 降级发送也失败: {channel}, 错误: {send_error}", exc_info=True)
                                # 更新转发统计信息（降级发送失败）
                                forward_interval_manager.update_statistics(success=False)
                                continue

                    # 输出转发统计摘要（如果有转发操作）
                    if remaining_channels:
                        self.logger.info(f"📊 转发统计: {forward_interval_manager.get_statistics_summary()}")

                # 步骤3：标记内容已发送
                self.mark_item_as_sent(source_url, content)
                sent_count += 1
                self.logger.info(f"✅ 内容处理完成 {i+1}/{len(sorted_items)}: 成功发送到 {len(successful_channels)} 个频道")

            except Exception as e:
                self.logger.error(f"💥 发送内容失败: {content.get('title', '无标题')}, 错误: {e}", exc_info=True)
                # 更新统计信息（发送失败）
                self.interval_manager.update_statistics(success=False)

                # 错误后等待
                if "flood control" in str(e).lower():
                    await self.interval_manager.wait_after_error("flood_control")
                elif "rate limit" in str(e).lower():
                    await self.interval_manager.wait_after_error("rate_limit")
                else:
                    await self.interval_manager.wait_after_error("other")
                continue

        self.logger.info(f"🎉 批量发送完成: 成功 {sent_count}/{len(content_items)} 个内容到 {len(target_channels)} 个频道")
        self.logger.info(f"📊 {self.interval_manager.get_statistics_summary()}")
        return sent_count

    def _sort_content_by_time(self, content_items: List[Dict]) -> List[Dict]:
        """
        按时间排序内容（从旧到新）

        Args:
            content_items: 内容列表

        Returns:
            List[Dict]: 排序后的内容列表
        """
        try:
            return sorted(content_items, key=lambda x: x.get('time', ''))
        except Exception as e:
            self.logger.warning(f"内容排序失败，使用原顺序: {e}")
            return content_items

    # ==================== 统计和维护接口 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取管理器统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            subscriptions = self.get_subscriptions()
            total_sources = len(subscriptions)
            total_channels = set()
            total_subscriptions = 0

            for channels in subscriptions.values():
                total_subscriptions += len(channels)
                total_channels.update(channels)

            return {
                "module_name": self.module_name,
                "total_sources": total_sources,
                "total_channels": len(total_channels),
                "total_subscriptions": total_subscriptions,
            }

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}", exc_info=True)
            return {}

    # ==================== 通用内容存储实现 ====================

    @staticmethod
    def datetime_handler(x):
        if isinstance(x, datetime):
            return x.isoformat()
        raise TypeError(f"Object of type {type(x)} is not JSON serializable")

    def _save_latest_content(self, source_url: str, all_content_data: List[Dict]):
        """
        保存最新内容引用（复用douyin模块的存储逻辑）

        Args:
            source_url: 数据源URL
            all_content_data: 全部内容数据列表
        """
        try:
            if not all_content_data:
                return

            # 保存最新内容引用（第一个）
            latest_content_info = all_content_data[0]  # 第一个是最新的
            url_hash = self._safe_filename(source_url)
            url_dir = self.data_storage_dir / url_hash
            url_dir.mkdir(parents=True, exist_ok=True)

            latest_file = url_dir / "latest.json"
            latest_file.write_text(
                json.dumps(latest_content_info, indent=2, ensure_ascii=False, default=self.datetime_handler),
                encoding='utf-8'
            )
            self.logger.debug(f"✅ 保存最新内容引用成功: {latest_file}")
        except Exception as e:
            self.logger.error(f"💥 保存最新内容引用失败: {source_url}, 错误: {str(e)}", exc_info=True)


# 便捷函数：创建统一管理器的工厂方法
def create_unified_manager(module_name: str, manager_class, **kwargs) -> UnifiedContentManager:
    """
    创建统一管理器实例的工厂方法

    Args:
        module_name: 模块名称
        manager_class: 具体的管理器类
        **kwargs: 传递给管理器构造函数的参数

    Returns:
        UnifiedContentManager: 统一管理器实例
    """
    return manager_class(module_name=module_name, **kwargs)


if __name__ == "__main__":
    # 模块测试代码
    def test_unified_manager():
        """测试统一管理器功能"""
        print("🧪 统一管理器模块测试")

        # 这里只能测试抽象接口，具体实现需要在子类中测试
        print("✅ 统一管理器基类定义完成")
        print("📝 子类需要实现所有抽象方法")
        print("🎯 提供了完整的业务逻辑复用")

        print("🎉 统一管理器模块测试完成")

    # 运行测试
    test_unified_manager()