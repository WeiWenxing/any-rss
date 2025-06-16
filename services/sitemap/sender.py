"""
Sitemap消息发送器模块

负责将Sitemap条目发送到Telegram。
提供简单的发送接口，只发送链接和更新时间。

作者: Assistant
创建时间: 2024年
"""

import logging
from typing import List, Optional
from datetime import datetime
from telegram import Bot

logger = logging.getLogger(__name__)

class SitemapSender:
    """Sitemap消息发送器"""

    def __init__(self):
        """初始化发送器"""
        self.logger = logging.getLogger(__name__)

    async def send_entry(self, bot: Bot, chat_id: str, url: str, last_modified: Optional[datetime] = None) -> List[int]:
        """
        发送Sitemap条目

        Args:
            bot: Telegram机器人实例
            chat_id: 聊天ID
            url: URL地址
            last_modified: 最后修改时间

        Returns:
            List[int]: 发送的消息ID列表
        """
        try:
            # 构建消息文本
            text = "🔗 *新链接*\n\n"
            text += f"*链接*: [{url}]({url})\n"
            
            if last_modified:
                text += f"*更新时间*: `{last_modified.strftime('%Y-%m-%d %H:%M:%S')}`\n"

            # 发送消息
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            
            return [sent_message.message_id]
            
        except Exception as e:
            self.logger.error(f"发送Sitemap消息失败: {str(e)}", exc_info=True)
            raise


# 便捷函数：创建Sitemap发送器实例
def create_sitemap_sender() -> SitemapSender:
    """
    创建Sitemap发送器实例

    Returns:
        SitemapSender: Sitemap发送器实例
    """
    return SitemapSender() 