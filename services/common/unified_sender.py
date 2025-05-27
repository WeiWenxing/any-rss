"""
统一Telegram发送器模块

该模块提供跨模块的统一Telegram消息发送功能，完全复用RSS模块的成熟媒体处理策略
和douyin模块的间隔管理机制。支持所有模块通过统一的TelegramMessage格式发送消息。

主要功能：
1. 统一消息发送接口
2. 集成RSS媒体策略（三层降级机制）
3. 集成douyin间隔管理（配置化分层时间控制）
4. 媒体组和文本消息的智能处理
5. 完整的容错和降级机制
6. 跨模块消息复制功能

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from telegram import Bot, Message
from telegram.error import TelegramError

from .telegram_message import TelegramMessage, MediaItem, MediaType
from .unified_interval_manager import UnifiedIntervalManager, create_unified_interval_manager


class UnifiedTelegramSender:
    """
    统一的Telegram发送器

    提供跨模块的统一消息发送功能，完全复用RSS模块的媒体处理策略。
    所有模块都可以通过TelegramMessage格式发送消息，享受统一的发送体验。
    """

    def __init__(self, interval_scenario: str = "default"):
        """
        初始化统一发送器

        Args:
            interval_scenario: 间隔管理场景 ("batch_send", "forward", "alignment", "rsshub_send", "default")
        """
        self.logger = logging.getLogger(__name__)
        self._media_strategy_cache = {}  # 缓存媒体策略管理器
        self.interval_manager = create_unified_interval_manager(interval_scenario)
        self.logger.info(f"统一发送器初始化完成，间隔场景: {interval_scenario}")

    async def send_message(self, bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]:
        """
        发送统一格式的Telegram消息

        这是所有模块的统一发送入口，根据消息类型自动选择最佳发送方式。

        Args:
            bot: Telegram Bot实例
            chat_id: 目标频道ID
            message: 统一格式的消息对象

        Returns:
            List[Message]: 发送成功的消息列表

        Raises:
            TelegramError: 发送失败时抛出异常
        """
        try:
            self.logger.info(f"开始发送统一消息到频道: {chat_id}")

            if message.media_group and len(message.media_group) > 0:
                # 媒体组发送：使用RSS媒体策略
                self.logger.info(f"检测到媒体组，包含 {len(message.media_group)} 个媒体项")
                return await self._send_media_group(bot, chat_id, message)
            else:
                # 文本消息发送
                self.logger.info("发送纯文本消息")
                sent_message = await self._send_text_message(bot, chat_id, message)
                return [sent_message]

        except Exception as e:
            self.logger.error(f"统一发送器发送失败: {str(e)}", exc_info=True)
            raise TelegramError(f"统一发送器发送失败: {str(e)}")

    async def send_batch_messages(
        self,
        bot: Bot,
        chat_id: str,
        messages: List[TelegramMessage]
    ) -> List[List[Message]]:
        """
        批量发送消息列表（集成douyin间隔管理）

        Args:
            bot: Telegram Bot实例
            chat_id: 目标频道ID
            messages: 要发送的消息列表

        Returns:
            List[List[Message]]: 每条消息的发送结果列表
        """
        results = []

        self.logger.info(f"开始批量发送 {len(messages)} 条消息，使用间隔场景: {self.interval_manager.scenario}")

        for i, message in enumerate(messages):
            try:
                # 发送前等待（使用douyin间隔管理逻辑）
                await self.interval_manager.wait_before_send(
                    content_index=i,
                    total_content=len(messages),
                    recent_error_rate=self.interval_manager.get_recent_error_rate()
                )

                self.logger.info(f"发送批量消息 {i+1}/{len(messages)}")
                sent_messages = await self.send_message(bot, chat_id, message)
                results.append(sent_messages)

                # 更新统计信息（发送成功）
                self.interval_manager.update_statistics(success=True)

            except Exception as e:
                self.logger.error(f"批量发送第{i+1}条消息失败: {str(e)}", exc_info=True)
                results.append([])  # 添加空结果

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

        # 输出统计摘要
        self.logger.info(f"📊 批量发送完成: {self.interval_manager.get_statistics_summary()}")

        return results

    async def copy_messages(self, bot: Bot, from_chat: str, to_chat: str, message_ids: List[int]) -> List[Message]:
        """
        复制消息（跨模块通用）

        使用copy_messages方法复制消息，不显示"Forward From"转发源标识，
        保持频道内容的一致性和美观性。

        Args:
            bot: Telegram Bot实例
            from_chat: 源频道ID
            to_chat: 目标频道ID
            message_ids: 要复制的消息ID列表

        Returns:
            List[Message]: 复制成功的消息列表
        """
        try:
            self.logger.info(f"开始复制消息: {from_chat} -> {to_chat}, {len(message_ids)}个消息")

            copied_messages = []

            for message_id in message_ids:
                try:
                    # 使用copy_message复制单个消息（不显示转发源）
                    copied_message = await bot.copy_message(
                        chat_id=to_chat,
                        from_chat_id=from_chat,
                        message_id=message_id
                    )
                    copied_messages.append(copied_message)

                    # 使用间隔管理器控制复制间隔
                    if len(copied_messages) < len(message_ids):
                        await self.interval_manager.wait_before_send(
                            content_index=len(copied_messages),
                            total_content=len(message_ids),
                            recent_error_rate=self.interval_manager.get_recent_error_rate()
                        )

                except TelegramError as e:
                    self.logger.error(f"复制单个消息失败 {message_id}: {str(e)}")
                    continue

            self.logger.info(f"消息复制完成: 成功 {len(copied_messages)}/{len(message_ids)} 个")
            return copied_messages

        except Exception as e:
            self.logger.error(f"批量复制消息失败: {str(e)}", exc_info=True)
            raise TelegramError(f"批量复制消息失败: {str(e)}")

    async def _send_media_group(self, bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]:
        """
        发送媒体组消息（完全复用RSS模块的媒体策略）

        使用RSS模块的三层降级机制：
        1. URL直接发送 → 2. 下载后上传 → 3. 文本降级

        Args:
            bot: Telegram Bot实例
            chat_id: 目标频道ID
            message: 包含媒体组的消息对象

        Returns:
            List[Message]: 发送成功的消息列表
        """
        try:
            # 导入RSS媒体策略（延迟导入避免循环依赖）
            from services.rss.media_strategy import create_media_strategy_manager

            # 创建或获取缓存的媒体策略管理器
            strategy_key = id(bot)  # 使用bot实例ID作为缓存键
            if strategy_key not in self._media_strategy_cache:
                strategy_manager, media_sender = create_media_strategy_manager(bot)
                self._media_strategy_cache[strategy_key] = (strategy_manager, media_sender)
                self.logger.info("创建RSS媒体策略管理器")
            else:
                strategy_manager, media_sender = self._media_strategy_cache[strategy_key]
                self.logger.debug("使用缓存的RSS媒体策略管理器")

            # 转换MediaItem为RSS媒体策略所需的格式
            media_list = []
            for media_item in message.media_group:
                media_dict = {
                    'url': media_item.url,
                    'type': self._convert_media_type(media_item.type)
                }
                media_list.append(media_dict)

            self.logger.info(f"准备使用RSS媒体策略发送 {len(media_list)} 个媒体项")

            # 分析媒体文件（可访问性、大小、策略决策）
            analyzed_media = strategy_manager.analyze_media_files(media_list)
            self.logger.info(f"媒体分析完成，策略决策: {[m.send_strategy.value for m in analyzed_media]}")

            # 使用RSS媒体策略发送
            success_messages = await media_sender.send_media_group_with_strategy(
                chat_id=chat_id,
                media_list=analyzed_media,
                caption=message.media_group[0].caption if message.media_group else None
            )

            if success_messages:
                self.logger.info(f"RSS媒体策略发送成功: {len(message.media_group)}个媒体项")
                return success_messages
            else:
                raise Exception("RSS媒体策略返回空结果")

        except Exception as e:
            self.logger.error(f"RSS媒体策略发送失败，降级到文本模式: {str(e)}", exc_info=True)

            # 降级到纯文本发送（启用链接预览作为媒体补偿）
            text_message = TelegramMessage(
                text=message.text,
                parse_mode=message.parse_mode,
                disable_web_page_preview=False  # 启用链接预览作为媒体补偿
            )

            self.logger.info("执行文本降级发送")
            sent_message = await self._send_text_message(bot, chat_id, text_message)
            return [sent_message]

    async def _send_text_message(self, bot: Bot, chat_id: str, message: TelegramMessage) -> Message:
        """
        发送文本消息

        Args:
            bot: Telegram Bot实例
            chat_id: 目标频道ID
            message: 文本消息对象

        Returns:
            Message: 发送成功的消息
        """
        try:
            self.logger.debug(f"发送文本消息到 {chat_id}")

            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=message.text,
                parse_mode=message.parse_mode,  # 直接使用，统一为字符串格式
                disable_web_page_preview=message.disable_web_page_preview,
                reply_markup=message.reply_markup
            )

            self.logger.info(f"文本消息发送成功: {sent_message.message_id}")
            return sent_message

        except Exception as e:
            self.logger.error(f"文本消息发送失败: {str(e)}", exc_info=True)
            raise TelegramError(f"文本消息发送失败: {str(e)}")

    def _convert_media_type(self, media_type: MediaType) -> str:
        """
        转换MediaType枚举为RSS媒体策略所需的字符串格式

        Args:
            media_type: MediaType枚举值

        Returns:
            str: RSS媒体策略所需的类型字符串
        """
        type_mapping = {
            MediaType.PHOTO: 'image',
            MediaType.VIDEO: 'video',
            MediaType.AUDIO: 'audio',
            MediaType.DOCUMENT: 'document'
        }

        return type_mapping.get(media_type, 'image')

    def clear_cache(self):
        """
        清理媒体策略缓存

        在Bot实例变更或需要重新初始化时调用
        """
        self._media_strategy_cache.clear()
        self.logger.info("已清理媒体策略缓存")


# 便捷函数：创建统一发送器实例
def create_unified_sender(interval_scenario: str = "default") -> UnifiedTelegramSender:
    """
    创建统一发送器实例

    Args:
        interval_scenario: 间隔管理场景 ("batch_send", "forward", "alignment", "rsshub_send", "default")

    Returns:
        UnifiedTelegramSender: 统一发送器实例
    """
    return UnifiedTelegramSender(interval_scenario)


# 便捷函数：快速发送消息
async def send_unified_message(bot: Bot, chat_id: str, message: TelegramMessage) -> List[Message]:
    """
    快速发送统一格式消息的便捷函数

    Args:
        bot: Telegram Bot实例
        chat_id: 目标频道ID
        message: 统一格式的消息对象

    Returns:
        List[Message]: 发送成功的消息列表
    """
    sender = create_unified_sender()
    return await sender.send_message(bot, chat_id, message)


# 便捷函数：快速复制消息
async def copy_unified_messages(bot: Bot, from_chat: str, to_chat: str, message_ids: List[int]) -> List[Message]:
    """
    快速复制消息的便捷函数

    Args:
        bot: Telegram Bot实例
        from_chat: 源频道ID
        to_chat: 目标频道ID
        message_ids: 要复制的消息ID列表

    Returns:
        List[Message]: 复制成功的消息列表
    """
    sender = create_unified_sender()
    return await sender.copy_messages(bot, from_chat, to_chat, message_ids)


if __name__ == "__main__":
    # 模块测试代码
    import asyncio
    from .telegram_message import TelegramMessage, MediaItem, MediaType

    async def test_unified_sender():
        """测试统一发送器功能"""
        print("🧪 统一发送器模块测试")

        # 测试创建发送器
        sender = create_unified_sender()
        print(f"✅ 创建统一发送器: {type(sender).__name__}")

        # 测试创建文本消息
        text_msg = TelegramMessage(text="测试消息", disable_web_page_preview=True)
        print(f"✅ 创建文本消息: {text_msg.text[:20]}...")

        # 测试创建媒体消息
        media_item = MediaItem(
            type=MediaType.PHOTO,
            url="https://example.com/image.jpg",
            caption="测试图片"
        )
        media_msg = TelegramMessage(
            text="测试媒体消息",
            media_group=[media_item]
        )
        print(f"✅ 创建媒体消息: {len(media_msg.media_group)}个媒体项")

        # 测试类型转换
        converted_type = sender._convert_media_type(MediaType.VIDEO)
        print(f"✅ 媒体类型转换: VIDEO -> {converted_type}")

        # 测试间隔管理器
        print(f"✅ 间隔管理器场景: {sender.interval_manager.scenario}")
        print(f"✅ 间隔管理器配置: {sender.interval_manager.get_config_summary()}")

        print("🎉 统一发送器模块测试完成")

    # 运行测试
    asyncio.run(test_unified_sender())