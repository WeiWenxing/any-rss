"""
抖音定时任务调度模块
负责协调抖音订阅的定时检查、消息发送和状态管理
"""

import logging
import asyncio
from telegram import Bot
from typing import Dict, Any, Tuple, List, Optional
from .manager import DouyinManager
from .commands import send_douyin_content


class DouyinScheduler:
    """抖音定时任务调度器"""

    def __init__(self):
        """初始化调度器"""
        self.douyin_manager = DouyinManager()
        logging.info("抖音定时任务调度器初始化完成")

    async def run_scheduled_check(self, bot: Bot) -> None:
        """
        执行抖音订阅的定时检查（支持多频道高效转发）

        Args:
            bot: Telegram Bot实例
        """
        try:
            subscriptions = self.douyin_manager.get_subscriptions()
            logging.info(f"定时任务开始检查抖音订阅更新，共 {len(subscriptions)} 个URL")

            # 统计信息
            total_new_content = 0
            success_count = 0
            error_count = 0

            # 遍历每个URL（而不是每个频道）
            for douyin_url, target_channels in subscriptions.items():
                try:
                    # 确保target_channels是列表格式
                    if isinstance(target_channels, str):
                        target_channels = [target_channels]

                    logging.info(f"正在检查抖音订阅: {douyin_url} -> 频道: {target_channels}")

                    # 处理单个URL的多频道订阅（使用高效转发）
                    new_content_count = await self.process_multi_channel_subscription(bot, douyin_url, target_channels)

                    if new_content_count > 0:
                        total_new_content += new_content_count
                        success_count += 1
                        logging.info(f"抖音订阅 {douyin_url} 处理成功，发送了 {new_content_count} 个新内容到 {len(target_channels)} 个频道")
                    else:
                        success_count += 1
                        logging.info(f"抖音订阅 {douyin_url} 无新增内容")

                except Exception as e:
                    error_count += 1
                    logging.error(f"处理抖音订阅失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
                    continue

            # 记录总结日志
            if total_new_content > 0:
                logging.info(f"抖音定时任务完成，共发现 {total_new_content} 个新内容")
            else:
                logging.info("抖音定时任务完成，无新增内容")

            logging.info(f"处理结果: 成功 {success_count} 个，失败 {error_count} 个")

        except Exception as e:
            logging.error(f"抖音定时任务执行失败: {str(e)}", exc_info=True)

    async def process_single_subscription(self, bot: Bot, douyin_url: str, target_chat_id: str) -> int:
        """
        处理单个抖音订阅的完整流程

        Args:
            bot: Telegram Bot实例
            douyin_url: 抖音用户链接
            target_chat_id: 目标聊天ID

        Returns:
            int: 发送的新内容数量
        """
        try:
            logging.info(f"开始处理抖音订阅: {douyin_url}")

            # 检查更新
            success, error_msg, new_items = self.douyin_manager.check_updates(douyin_url)

            if not success:
                logging.warning(f"抖音订阅 {douyin_url} 检查失败: {error_msg}")
                return 0

            # 如果有新内容，逐个发送通知
            if new_items and len(new_items) > 0:
                logging.info(f"抖音订阅 {douyin_url} 发现 {len(new_items)} 个新内容")

                # 根据内容数量选择处理策略
                is_large_batch = len(new_items) >= 10
                if is_large_batch:
                    logging.info(f"🚀 启用大批量处理模式: {len(new_items)} 个内容")
                else:
                    logging.info(f"📤 启用常规处理模式: {len(new_items)} 个内容")

                sent_count = await self._process_batch(bot, new_items, douyin_url, target_chat_id)

                logging.info(f"抖音订阅 {douyin_url} 发送完成，成功 {sent_count}/{len(new_items)} 个")
                return sent_count
            else:
                logging.info(f"抖音订阅 {douyin_url} 无新增内容")
                return 0

        except Exception as e:
            logging.error(f"处理抖音订阅失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return 0

    async def _send_notification_safe(
        self, bot: Bot, content_info: dict, douyin_url: str, target_chat_id: str
    ) -> Tuple[bool, Optional[int]]:
        """
        安全地发送通知，返回发送结果和消息ID

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            douyin_url: 抖音用户链接
            target_chat_id: 目标聊天ID

        Returns:
            Tuple[bool, Optional[int]]: (是否发送成功, 消息ID)
        """
        try:
            message = await send_douyin_content(bot, content_info, douyin_url, target_chat_id)

            # 提取消息ID
            if hasattr(message, 'message_id'):
                return True, message.message_id
            elif isinstance(message, list) and len(message) > 0:
                # 如果是图片组，返回第一张图片的消息ID
                return True, message[0].message_id
            else:
                return True, None
        except Exception as e:
            logging.error(f"发送抖音通知失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return False, None

    def get_subscription_count(self) -> int:
        """
        获取当前订阅数量

        Returns:
            int: 订阅数量
        """
        try:
            subscriptions = self.douyin_manager.get_subscriptions()
            return len(subscriptions)
        except Exception as e:
            logging.error(f"获取抖音订阅数量失败: {str(e)}", exc_info=True)
            return 0

    def cleanup_old_files(self) -> None:
        """清理过期的文件（预留接口，抖音模块暂时不需要）"""
        try:
            # 抖音模块暂时不需要清理逻辑
            # 如果将来需要清理下载的媒体文件，可以在这里实现
            logging.info("抖音模块清理任务完成（暂无需清理的文件）")
        except Exception as e:
            logging.error(f"抖音模块清理文件失败: {str(e)}", exc_info=True)

    async def _process_batch(self, bot: Bot, new_items: List[Dict], douyin_url: str, target_chat_id: str) -> int:
        """
        处理批量内容，使用统一的发送策略

        Args:
            bot: Telegram Bot实例
            new_items: 新内容列表
            douyin_url: 抖音用户链接
            target_chat_id: 目标聊天ID

        Returns:
            int: 发送成功的内容数量
        """
        from .interval_manager import MessageSendingIntervalManager

        # 初始化间隔管理器（批量发送场景）
        interval_manager = MessageSendingIntervalManager("batch_send")

        # 按发布时间排序（从旧到新）
        sorted_items = self.douyin_manager._sort_content_by_time(new_items)

        sent_count = 0
        for i, content_info in enumerate(sorted_items):
            try:
                # 发送前等待（使用配置化间隔管理器）
                await interval_manager.wait_before_send(
                    content_index=i,
                    total_content=len(sorted_items),
                    recent_error_rate=interval_manager.get_recent_error_rate()
                )

                # 发送单个内容
                send_success, message_id = await self._send_notification_safe(
                    bot, content_info, douyin_url, target_chat_id
                )

                if send_success:
                    # 发送成功，标记为已发送
                    self.douyin_manager.mark_item_as_sent(douyin_url, content_info)
                    sent_count += 1
                    logging.info(f"抖音订阅 {douyin_url} 第 {i+1}/{len(sorted_items)} 个内容发送成功")
                    # 更新统计信息（发送成功）
                    interval_manager.update_statistics(success=True)
                else:
                    logging.warning(f"抖音订阅 {douyin_url} 第 {i+1}/{len(sorted_items)} 个内容发送失败，下次将重试")
                    # 更新统计信息（发送失败）
                    interval_manager.update_statistics(success=False)

            except Exception as e:
                logging.error(f"发送抖音内容失败: {douyin_url} 第 {i+1} 个, 错误: {str(e)}", exc_info=True)
                # 更新统计信息（发送失败）
                interval_manager.update_statistics(success=False)

                # 错误后等待
                if "flood control" in str(e).lower():
                    await interval_manager.wait_after_error("flood_control")
                elif "rate limit" in str(e).lower():
                    await interval_manager.wait_after_error("rate_limit")
                else:
                    await interval_manager.wait_after_error("other")
                continue

        logging.info(f"📊 {interval_manager.get_statistics_summary()}")
        return sent_count

    async def process_multi_channel_subscription(self, bot: Bot, douyin_url: str, target_channels: List[str]) -> int:
        """
        处理单个URL的多频道订阅（高效转发机制）

        Args:
            bot: Telegram Bot实例
            douyin_url: 抖音用户链接
            target_channels: 目标频道列表

        Returns:
            int: 发送的新内容数量
        """
        try:
            logging.info(f"开始处理多频道抖音订阅: {douyin_url} -> {len(target_channels)} 个频道")

            # 检查更新（返回的内容已包含target_channels信息）
            success, error_msg, new_items = self.douyin_manager.check_updates(douyin_url)

            if not success:
                logging.warning(f"抖音订阅 {douyin_url} 检查失败: {error_msg}")
                return 0

            # 如果有新内容，使用高效转发机制
            if new_items and len(new_items) > 0:
                logging.info(f"抖音订阅 {douyin_url} 发现 {len(new_items)} 个新内容，将发送到 {len(target_channels)} 个频道")

                # 使用高效转发批量处理
                sent_count = await self._process_batch_with_forwarding(bot, new_items, douyin_url, target_channels)

                logging.info(f"抖音订阅 {douyin_url} 发送完成，成功 {sent_count}/{len(new_items)} 个")
                return sent_count
            else:
                logging.info(f"抖音订阅 {douyin_url} 无新增内容")
                return 0

        except Exception as e:
            logging.error(f"处理多频道抖音订阅失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return 0

    async def _process_batch_with_forwarding(self, bot: Bot, new_items: List[Dict], douyin_url: str, target_channels: List[str]) -> int:
        """
        使用高效转发机制处理批量内容

        Args:
            bot: Telegram Bot实例
            new_items: 新内容列表
            douyin_url: 抖音用户链接
            target_channels: 目标频道列表

        Returns:
            int: 发送成功的内容数量
        """
        # 直接使用Manager的批量发送方法
        return await self.douyin_manager.send_content_batch(bot, new_items, douyin_url, target_channels)


# 创建全局调度器实例
douyin_scheduler = DouyinScheduler()


# 导出函数供telegram_bot调用
async def run_scheduled_check(bot: Bot) -> None:
    """
    抖音定时检查入口函数

    Args:
        bot: Telegram Bot实例
    """
    await douyin_scheduler.run_scheduled_check(bot)