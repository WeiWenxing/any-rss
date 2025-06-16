"""
Sitemap消息发送器模块

该模块负责将Sitemap内容发送到Telegram，完全复用rsshub模块的发送逻辑。
支持文本消息、媒体消息的发送，以及多频道转发功能。

主要功能：
1. 文本消息发送
2. 媒体消息发送
3. 多频道转发
4. 发送状态管理
5. 错误处理和重试

作者: Assistant
创建时间: 2024年
"""

import logging
from typing import List, Dict, Any, Optional
from telegram import Bot, Message

from services.common.unified_sender import UnifiedTelegramSender


class SitemapSender(UnifiedTelegramSender):
    """
    Sitemap消息发送器

    继承统一发送器基类，完全复用rsshub模块的发送逻辑
    """

    def __init__(self):
        """初始化Sitemap发送器"""
        super().__init__(interval_scenario="default")
        self.logger.info("Sitemap发送器初始化完成")

    async def send_entry(self, bot: Bot, chat_id: str, url: str, last_modified: Optional[str] = None) -> List[int]:
        """
        发送Sitemap条目

        Args:
            bot: Telegram Bot实例
            chat_id: 目标聊天ID
            url: 条目URL
            last_modified: 最后修改时间

        Returns:
            List[int]: 发送的消息ID列表
        """
        try:
            self.logger.info(f"开始发送Sitemap条目: {url}")

            # 构建消息文本
            message_text = f"🔗 {url}"
            if last_modified:
                message_text += f"\n\n📅 更新时间: {last_modified}"

            # 发送消息
            message = await self.send_text_message(
                bot=bot,
                chat_id=chat_id,
                text=message_text,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )

            self.logger.info(f"✅ Sitemap条目发送成功: {url}")
            return [message.message_id]

        except Exception as e:
            self.logger.error(f"❌ 发送Sitemap条目失败: {url}, 错误: {str(e)}", exc_info=True)
            raise


def create_sitemap_sender() -> SitemapSender:
    """
    创建Sitemap发送器实例

    Returns:
        SitemapSender: 发送器实例
    """
    return SitemapSender() 