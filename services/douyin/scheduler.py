"""
抖音定时任务调度模块
负责协调抖音订阅的定时检查、消息发送和状态管理
"""

import logging
import asyncio
from telegram import Bot
from typing import Dict, Any, Tuple
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
        执行抖音订阅的定时检查

        Args:
            bot: Telegram Bot实例
        """
        try:
            subscriptions = self.douyin_manager.get_subscriptions()
            logging.info(f"定时任务开始检查抖音订阅更新，共 {len(subscriptions)} 个订阅")

            # 统计信息
            total_new_content = 0
            success_count = 0
            error_count = 0

            for douyin_url, subscription_info in subscriptions.items():
                try:
                    target_chat_id = subscription_info.get("chat_id", "")
                    logging.info(f"正在检查抖音订阅: {douyin_url} -> 频道: {target_chat_id}")

                    # 处理单个抖音订阅
                    new_content_count = await self.process_single_subscription(bot, douyin_url, target_chat_id)

                    if new_content_count > 0:
                        total_new_content += new_content_count
                        success_count += 1
                        logging.info(f"抖音订阅 {douyin_url} 处理成功，发送了 {new_content_count} 个新内容")
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

                sent_count = 0
                for i, content_info in enumerate(new_items):
                    try:
                        # 发送单个内容
                        send_success = await self._send_notification_safe(
                            bot, content_info, douyin_url, target_chat_id
                        )

                        if send_success:
                            # 发送成功，标记为已发送
                            self.douyin_manager.mark_item_as_sent(douyin_url, content_info)
                            sent_count += 1
                            logging.info(f"抖音订阅 {douyin_url} 第 {i+1}/{len(new_items)} 个内容发送成功")
                        else:
                            logging.warning(f"抖音订阅 {douyin_url} 第 {i+1}/{len(new_items)} 个内容发送失败，下次将重试")

                        # 添加发送间隔，避免频率限制
                        if i < len(new_items) - 1:  # 不是最后一个
                            await asyncio.sleep(1)  # 等待1秒

                    except Exception as e:
                        logging.error(f"发送抖音内容失败: {douyin_url} 第 {i+1} 个, 错误: {str(e)}", exc_info=True)
                        continue

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