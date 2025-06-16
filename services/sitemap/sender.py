"""
Sitemap消息发送器模块

该模块负责将Sitemap内容发送到Telegram频道，继承自UnifiedTelegramSender。
提供Sitemap特定的消息发送逻辑。

主要功能：
1. 发送Sitemap条目
2. 处理发送错误
3. 管理发送间隔

作者: Assistant
创建时间: 2024年
"""

import logging
from typing import List, Optional
from telegram import Bot, Message

from services.common.unified_sender import UnifiedTelegramSender
from services.common.telegram_message import TelegramMessage


class SitemapSender(UnifiedTelegramSender):
    """
    Sitemap消息发送器

    继承统一Telegram发送器基类，实现Sitemap特定的发送逻辑
    """

    def __init__(self):
        """
        初始化Sitemap发送器
        """
        super().__init__(interval_scenario="default")
        self.logger = logging.getLogger(__name__)

    async def send_message(self, bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]:
        """
        发送Sitemap消息

        Args:
            bot: Telegram Bot实例
            chat_id: 目标聊天ID
            message: TelegramMessage对象

        Returns:
            List[Message]: 发送的消息列表
        """
        try:
            self.logger.info(f"开始发送Sitemap消息: {message.text}")

            # 直接使用bot发送消息
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=message.text,
                parse_mode=message.parse_mode,
                disable_web_page_preview=message.disable_web_page_preview
            )

            self.logger.info(f"✅ Sitemap消息发送成功: {message.text}")
            return [sent_message]

        except Exception as e:
            self.logger.error(f"❌ 发送Sitemap消息失败: {message.text}, 错误: {str(e)}", exc_info=True)
            raise


def create_sitemap_sender() -> SitemapSender:
    """
    创建Sitemap发送器实例

    Returns:
        SitemapSender: 发送器实例
    """
    return SitemapSender()