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
from telegram import Bot

from services.common.unified_sender import UnifiedTelegramSender


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

    async def send_message(self, bot: Bot, chat_id: str, content: dict) -> List[int]:
        """
        发送Sitemap消息

        Args:
            bot: Telegram Bot实例
            chat_id: 目标聊天ID
            content: 消息内容，包含url和last_modified字段

        Returns:
            List[int]: 发送的消息ID列表
        """
        try:
            self.logger.info(f"开始发送Sitemap消息: {content.get('url')}")

            # 构建消息文本
            message_text = f"🔗 {content['url']}"
            if content.get('last_modified'):
                message_text += f"\n\n📅 更新时间: {content['last_modified']}"

            # 直接使用bot发送消息
            message = await bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )

            self.logger.info(f"✅ Sitemap消息发送成功: {content.get('url')}")
            return [message.message_id]

        except Exception as e:
            self.logger.error(f"❌ 发送Sitemap消息失败: {content.get('url')}, 错误: {str(e)}", exc_info=True)
            raise


def create_sitemap_sender() -> SitemapSender:
    """
    创建Sitemap发送器实例

    Returns:
        SitemapSender: 发送器实例
    """
    return SitemapSender()