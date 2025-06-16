"""
Sitemap管理器模块

该模块负责管理Sitemap订阅和内容更新，继承自UnifiedContentManager。
提供Sitemap URL的订阅管理、内容检查和更新推送功能。

主要功能：
1. Sitemap URL的订阅管理
2. 内容更新检查
3. 多频道推送
4. 历史内容对齐
5. 错误处理和恢复

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
from pathlib import Path
from telegram import Bot

from services.common.unified_manager import UnifiedContentManager
from .sitemap_parser import SitemapParser, create_sitemap_parser
from services.common.message_converter import get_converter, ConverterType
from .converter import create_sitemap_converter
from .sender import create_sitemap_sender


class SitemapManager(UnifiedContentManager):
    """
    Sitemap管理器

    继承统一内容管理器基类，实现Sitemap特定的业务逻辑
    """

    def __init__(self, data_dir: str = "storage/sitemap"):
        """
        初始化Sitemap管理器

        Args:
            data_dir: 数据存储目录
        """
        super().__init__("sitemap", data_dir)

        # 初始化Sitemap特定组件
        self.parser = create_sitemap_parser()
        self.sender = create_sitemap_sender()
        self.sitemap_converter = create_sitemap_converter()

        self.logger.info("Sitemap管理器初始化完成")

    async def fetch_latest_content(self, source_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取最新内容

        Args:
            source_url: Sitemap URL

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 消息, 内容列表)
        """
        try:
            # 解析Sitemap
            entries = await self.parser.parse_sitemap(source_url)

            # 过滤已知内容
            new_entries = []
            for entry in entries:
                if not self.is_known_item(source_url, entry['url']):
                    new_entries.append(entry)

            if not new_entries:
                return True, "没有新内容", None

            # 按时间排序
            new_entries = self._sort_content_by_time(new_entries)

            # 只返回最近的10个内容
            new_entries = new_entries[:10]

            return True, "success", new_entries

        except Exception as e:
            self.logger.error(f"获取最新内容失败: {str(e)}", exc_info=True)
            return False, str(e), None

    def generate_content_id(self, content_data: Dict) -> str:
        """
        生成内容ID

        Args:
            content_data: 内容数据

        Returns:
            str: 内容ID
        """
        # 使用URL作为内容ID
        return content_data['url']

    def _get_module_converter(self):
        """
        获取模块转换器

        Returns:
            MessageConverter: 消息转换器
        """
        return self.sitemap_converter

    def _sort_content_by_time(self, content_items: List[Dict]) -> List[Dict]:
        """
        按时间排序内容

        Args:
            content_items: 内容列表

        Returns:
            List[Dict]: 排序后的内容列表
        """
        def get_time(item: Dict) -> datetime:
            if 'last_modified' in item:
                return item['last_modified']
            return datetime.min

        return sorted(content_items, key=get_time, reverse=True)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = super().get_statistics()
        stats.update({
            'module': 'sitemap',
            'description': 'Sitemap订阅统计'
        })
        return stats


def create_sitemap_manager(data_dir: str = "storage/sitemap") -> SitemapManager:
    """
    创建Sitemap管理器实例

    Args:
        data_dir: 数据存储目录

    Returns:
        SitemapManager: 管理器实例
    """
    return SitemapManager(data_dir)