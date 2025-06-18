"""
Sitemap消息转换器

将Sitemap条目转换为Telegram消息格式。
继承MessageConverter，实现简单的URL和lastmod转换。

作者: Assistant
创建时间: 2024年
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from services.common.message_converter import MessageConverter, ConverterType
from services.common.telegram_message import TelegramMessage, MediaItem, MediaType


class SitemapConverter(MessageConverter):
    """Sitemap消息转换器"""

    def __init__(self):
        """初始化转换器"""
        super().__init__(ConverterType.GENERIC)
        self.logger = logging.getLogger("sitemap.converter")
        self.logger.info("Sitemap消息转换器初始化完成")

    def convert(self, source_data: Any, **kwargs) -> TelegramMessage:
        """
        转换内容数据为消息格式

        Args:
            source_data: 内容数据，包含url和last_modified
            **kwargs: 额外参数

        Returns:
            TelegramMessage: 转换后的消息
        """
        try:
            # 获取URL和最后修改时间
            url = source_data.get('url')
            last_modified = source_data.get('last_modified')

            if not url:
                self.logger.error("内容数据缺少URL")
                raise ValueError("内容数据缺少URL")

            # 构建消息文本
            message_text = f"链接： `{url}`"
            if last_modified:
                message_text += f"\n\n更新时间: `{last_modified.strftime('%Y-%m-%d %H:%M:%S')}`"

            # 创建消息
            return TelegramMessage.create_text_message(
                text=message_text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )

        except Exception as e:
            self.logger.error(f"转换内容失败: {str(e)}", exc_info=True)
            raise

    def convert_batch(self, source_data_list: List[Any], **kwargs) -> List[TelegramMessage]:
        """
        批量转换内容数据

        Args:
            source_data_list: 内容数据列表
            **kwargs: 额外参数

        Returns:
            List[TelegramMessage]: 转换后的消息列表
        """
        messages = []
        for data in source_data_list:
            try:
                message = self.convert(data, **kwargs)
                messages.append(message)
            except Exception as e:
                self.logger.error(f"批量转换失败: {str(e)}", exc_info=True)
                # 尝试降级处理
                fallback_message = self.handle_conversion_error(e, data)
                if fallback_message:
                    messages.append(fallback_message)
        return messages

    def get_source_display_name(self, source_url: str) -> str:
        """
        获取数据源显示名称

        Args:
            source_url: 数据源URL

        Returns:
            str: 显示名称
        """
        return f"Sitemap: {source_url}"


def create_sitemap_converter() -> SitemapConverter:
    """
    创建Sitemap转换器实例

    Returns:
        SitemapConverter: 转换器实例
    """
    return SitemapConverter() 