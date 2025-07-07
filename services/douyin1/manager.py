"""
模块管理器

该模块负责管理账号订阅和内容更新，继承自UnifiedContentManager。
提供账号的订阅管理、内容检查和更新推送功能。

主要功能：
1. 账号的订阅管理
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
from services.common.message_converter import get_converter, ConverterType
from . import MODULE_NAME, MODULE_DISPLAY_NAME, MODULE_DESCRIPTION, DATA_DIR_PREFIX
from .fetcher import DouyinFetcher
from .converter import DouyinConverter


class ContentManager(UnifiedContentManager):
    """
    内容管理器

    继承统一内容管理器基类，实现特定的业务逻辑
    """

    def __init__(self, data_dir: str = None):
        """
        初始化内容管理器

        Args:
            data_dir: 数据存储目录（可选，默认使用模块配置）
        """
        if data_dir is None:
            data_dir = DATA_DIR_PREFIX

        super().__init__(MODULE_NAME, data_dir)

        # 初始化特定组件
        self.fetcher = DouyinFetcher()
        self.message_converter = DouyinConverter()

        self.logger.info(f"{MODULE_DISPLAY_NAME}管理器初始化完成")

    def fetch_latest_content(self, source_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取最新内容

        Args:
            source_url: 账号URL

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 消息, 内容列表)
        """
        try:
            self.logger.info(f"获取最新内容: {source_url}")

            # 验证抖音URL格式
            if not self.fetcher.validate_douyin_url(source_url):
                return False, "无效的抖音URL格式", None

            # 使用获取器获取内容
            success, message, content_list = self.fetcher.fetch_user_content(source_url)

            if not success:
                return False, message, None

            if not content_list:
                return True, "没有新内容", None

            # 过滤已知内容
            new_content = []
            for content_data in content_list:
                content_id = self.generate_content_id(content_data)
                if not self.is_known_item(source_url, content_id):
                    new_content.append(content_data)

            if not new_content:
                return True, "没有新内容", None

            # 按时间排序
            new_content = self._sort_content_by_time(new_content)

            # 只返回最近的10个内容
            # new_content = new_content[:10]

            self.logger.info(f"获取到 {len(new_content)} 个新内容")
            return True, "success", new_content

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
        # 使用抖音视频的aweme_id作为内容标识
        return content_data.get('aweme_id', content_data.get('id', 'unknown'))

    def _sort_content_by_time(self, content_list: List[Dict]) -> List[Dict]:
        """
        按时间排序内容列表

        Args:
            content_list: 内容列表

        Returns:
            List[Dict]: 排序后的内容列表（从旧到新）
        """
        try:
            # 按create_time字段排序（Unix时间戳）
            return sorted(
                content_list,
                key=lambda x: x.get('create_time', 0),
                reverse=False  # 最旧的在前（从旧到新）
            )
        except Exception as e:
            self.logger.error(f"内容排序失败: {str(e)}", exc_info=True)
            return content_list

    def _get_module_converter(self):
        """
        获取模块转换器

        Returns:
            MessageConverter: 消息转换器
        """
        return self.message_converter

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = super().get_statistics()
        stats.update({
            'module': MODULE_NAME,
            'display_name': MODULE_DISPLAY_NAME,
            'description': MODULE_DESCRIPTION,
            'features': [
                '账号订阅',
                '自动内容推送',
                '多频道支持',
                '历史对齐'
            ]
        })
        return stats


def create_content_manager(data_dir: str = None) -> ContentManager:
    """
    创建内容管理器实例

    Args:
        data_dir: 数据存储目录（可选，默认使用模块配置）

    Returns:
        ContentManager: 管理器实例
    """
    return ContentManager(data_dir)