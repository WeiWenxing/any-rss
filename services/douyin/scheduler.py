"""
抖音定时任务调度模块
负责协调抖音订阅的定时检查、消息发送和状态管理
"""

import logging
import asyncio
from telegram import Bot
from typing import Dict, Any, Tuple, List
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
    ) -> bool:
        """
        安全地发送通知，捕获异常并返回发送结果

        Args:
            bot: Telegram Bot实例
            content_info: 内容信息
            douyin_url: 抖音用户链接
            target_chat_id: 目标聊天ID

        Returns:
            bool: 是否发送成功
        """
        try:
            await send_douyin_content(bot, content_info, douyin_url, target_chat_id)
            return True
        except Exception as e:
            logging.error(f"发送抖音通知失败: {douyin_url}, 错误: {str(e)}", exc_info=True)
            return False

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
        # 按发布时间排序（从旧到新）
        sorted_items = self._sort_items_by_time(new_items)

        sent_count = 0
        for i, content_info in enumerate(sorted_items):
            try:
                # 发送单个内容
                send_success = await self._send_notification_safe(
                    bot, content_info, douyin_url, target_chat_id
                )

                if send_success:
                    # 发送成功，标记为已发送
                    self.douyin_manager.mark_item_as_sent(douyin_url, content_info)
                    sent_count += 1
                    logging.info(f"抖音订阅 {douyin_url} 第 {i+1}/{len(sorted_items)} 个内容发送成功")
                else:
                    logging.warning(f"抖音订阅 {douyin_url} 第 {i+1}/{len(sorted_items)} 个内容发送失败，下次将重试")

                # 发送间隔策略
                if i < len(sorted_items) - 1:  # 不是最后一个
                    if (i + 1) % 10 == 0:  # 每10条消息暂停1分钟（只有大批量模式才可能达到）
                        logging.info(f"📦 已发送10个内容，暂停60秒避免flood exceed...")
                        await asyncio.sleep(60)
                    else:
                        # 统一的8秒间隔（大批量的常规间隔 + 常规模式的间隔）
                        logging.debug(f"等待8秒后发送下一个抖音内容...")
                        await asyncio.sleep(8)

            except Exception as e:
                logging.error(f"发送抖音内容失败: {douyin_url} 第 {i+1} 个, 错误: {str(e)}", exc_info=True)
                # 出错后也要等待，避免连续错误
                await asyncio.sleep(5)
                continue

        return sent_count

    def _sort_items_by_time(self, items: List[Dict]) -> List[Dict]:
        """
        按发布时间排序内容列表（从旧到新）

        Args:
            items: 内容列表

        Returns:
            List[Dict]: 排序后的内容列表
        """
        try:
            def get_sort_key(item):
                """获取排序键"""
                time_str = item.get("time", "")
                if not time_str:
                    # 没有时间信息的放到最后
                    return "9999-12-31"

                # 处理不同的时间格式
                if isinstance(time_str, str):
                    # 如果是日期格式如 "2025-03-05"，直接返回
                    if len(time_str) >= 10 and time_str[4] == '-' and time_str[7] == '-':
                        return time_str
                    # 如果是其他格式，尝试提取日期部分
                    import re
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', time_str)
                    if date_match:
                        return date_match.group(1)

                # 无法解析的时间格式，使用原始字符串
                return str(time_str)

            # 排序（从旧到新）
            sorted_items = sorted(items, key=get_sort_key)

            # 记录排序信息
            if len(items) > 1:
                first_time = sorted_items[0].get("time", "Unknown")
                last_time = sorted_items[-1].get("time", "Unknown")
                logging.info(f"📅 内容按时间排序完成: {len(items)} 个内容，时间范围: {first_time} ~ {last_time}")

            return sorted_items

        except Exception as e:
            logging.error(f"排序内容失败: {str(e)}", exc_info=True)
            # 排序失败时返回原列表
            return items

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
        if not target_channels:
            return 0

        # 按发布时间排序（从旧到新）
        sorted_items = self._sort_items_by_time(new_items)

        # 选择主频道（第一个频道）
        primary_channel = target_channels[0]
        secondary_channels = target_channels[1:]

        sent_count = 0
        for i, content_info in enumerate(sorted_items):
            try:
                # 步骤1：发送到主频道
                send_success = await self._send_notification_safe(
                    bot, content_info, douyin_url, primary_channel
                )

                if send_success:
                    # 获取发送的消息ID（用于转发）
                    # TODO: 需要修改_send_notification_safe返回消息ID
                    item_id = self.douyin_manager.fetcher.generate_content_id(content_info)

                    # 步骤2：转发到其他频道
                    for secondary_channel in secondary_channels:
                        try:
                            # TODO: 实施转发逻辑
                            # primary_message_id = self.douyin_manager.get_message_id(douyin_url, item_id, primary_channel)
                            # if primary_message_id:
                            #     await bot.forward_message(
                            #         chat_id=secondary_channel,
                            #         from_chat_id=primary_channel,
                            #         message_id=primary_message_id
                            #     )
                            logging.info(f"TODO: 转发内容 {item_id} 从 {primary_channel} 到 {secondary_channel}")
                        except Exception as e:
                            logging.error(f"转发失败，降级为直接发送: {secondary_channel}, 错误: {str(e)}")
                            # 转发失败，降级为直接发送
                            await self._send_notification_safe(
                                bot, content_info, douyin_url, secondary_channel
                            )

                    # 发送成功，标记为已发送
                    self.douyin_manager.mark_item_as_sent(douyin_url, content_info)
                    sent_count += 1
                    logging.info(f"抖音订阅 {douyin_url} 第 {i+1}/{len(sorted_items)} 个内容发送成功到 {len(target_channels)} 个频道")
                else:
                    logging.warning(f"抖音订阅 {douyin_url} 第 {i+1}/{len(sorted_items)} 个内容发送失败，下次将重试")

                # 发送间隔策略
                if i < len(sorted_items) - 1:  # 不是最后一个
                    if (i + 1) % 10 == 0:  # 每10条消息暂停1分钟
                        logging.info(f"📦 已发送10个内容，暂停60秒避免flood exceed...")
                        await asyncio.sleep(60)
                    else:
                        # 统一的8秒间隔
                        logging.debug(f"等待8秒后发送下一个抖音内容...")
                        await asyncio.sleep(8)

            except Exception as e:
                logging.error(f"处理内容失败: {douyin_url}, 第 {i+1} 个内容, 错误: {str(e)}", exc_info=True)
                continue

        return sent_count


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