"""
RSS定时任务调度模块
负责协调RSS订阅的定时检查、消息发送和状态管理
"""

import logging
import asyncio
from telegram import Bot
from typing import List, Tuple
from .manager import RSSManager
from .state_manager import FeedStateManager
from .message_sender import send_update_notification


class RSSScheduler:
    """RSS定时任务调度器"""
    
    def __init__(self):
        """初始化调度器"""
        self.rss_manager = RSSManager()
        self.state_manager = FeedStateManager(self.rss_manager.feeds_data_dir)
        logging.info("RSS定时任务调度器初始化完成")
    
    async def run_scheduled_check(self, bot: Bot) -> None:
        """
        执行RSS订阅的定时检查
        
        Args:
            bot: Telegram Bot实例
        """
        try:
            feeds = self.rss_manager.get_feeds()
            logging.info(f"定时任务开始检查RSS订阅源更新，共 {len(feeds)} 个订阅")
            
            # 统计信息
            total_new_entries = 0
            success_count = 0
            error_count = 0
            
            for url, target_chat_id in feeds.items():
                try:
                    logging.info(f"正在检查RSS订阅源: {url} -> 频道: {target_chat_id}")
                    
                    # 处理单个Feed
                    new_entries_count = await self.process_single_feed(bot, url, target_chat_id)
                    
                    if new_entries_count > 0:
                        total_new_entries += new_entries_count
                        success_count += 1
                        logging.info(f"RSS订阅源 {url} 处理成功，发送了 {new_entries_count} 个新条目")
                    else:
                        success_count += 1
                        logging.info(f"RSS订阅源 {url} 无新增内容")
                        
                except Exception as e:
                    error_count += 1
                    logging.error(f"处理RSS订阅源失败: {url}, 错误: {str(e)}")
                    continue
            
            # 记录总结日志
            if total_new_entries > 0:
                logging.info(f"RSS定时任务完成，共发现 {total_new_entries} 个新条目")
            else:
                logging.info("RSS定时任务完成，无新增内容")
                
            logging.info(f"处理结果: 成功 {success_count} 个，失败 {error_count} 个")
            
        except Exception as e:
            logging.error(f"RSS定时任务执行失败: {str(e)}", exc_info=True)
    
    async def process_single_feed(self, bot: Bot, url: str, target_chat_id: str) -> int:
        """
        处理单个Feed的完整流程
        
        Args:
            bot: Telegram Bot实例
            url: Feed URL
            target_chat_id: 目标聊天ID
            
        Returns:
            int: 发送的新条目数量
        """
        try:
            feed_dir = self.rss_manager._get_feed_dir(url)
            
            # 1. 检查是否有pending状态（已下载但未发送）
            if self.state_manager.is_pending(feed_dir):
                logging.info(f"发现pending状态，重新发送之前的内容: {url}")
                return await self._handle_pending_feed(bot, url, target_chat_id, feed_dir)
            
            # 2. 检查Feed更新
            success, error_msg, xml_content, new_entries = self.rss_manager.download_and_parse_feed(url)
            
            if not success:
                if "今天已经更新过此Feed" in error_msg:
                    logging.info(f"RSS订阅源 {url} {error_msg}")
                    return 0
                else:
                    logging.warning(f"RSS订阅源 {url} 更新失败: {error_msg}")
                    return 0
            
            # 3. 如果有新内容，创建pending文件并发送
            if new_entries:
                logging.info(f"RSS订阅源 {url} 发现 {len(new_entries)} 个新条目")
                
                # 创建pending文件
                if self.state_manager.create_pending_file(feed_dir, new_entries, xml_content):
                    # 发送通知
                    send_success = await self._send_notification_safe(
                        bot, url, new_entries, xml_content, target_chat_id
                    )
                    
                    # 根据发送结果处理pending状态
                    if send_success:
                        self.state_manager.delete_pending_file(feed_dir)
                        logging.info(f"RSS订阅源 {url} 发送成功，已清理pending状态")
                        return len(new_entries)
                    else:
                        logging.warning(f"RSS订阅源 {url} 发送失败，保留pending状态以便重试")
                        return 0
                else:
                    logging.error(f"RSS订阅源 {url} 创建pending文件失败")
                    return 0
            else:
                logging.info(f"RSS订阅源 {url} 无新增内容")
                return 0
                
        except Exception as e:
            logging.error(f"处理Feed失败: {url}, 错误: {str(e)}")
            return 0
    
    async def _handle_pending_feed(self, bot: Bot, url: str, target_chat_id: str, feed_dir) -> int:
        """
        处理pending状态的Feed（重新发送之前的内容）
        
        Args:
            bot: Telegram Bot实例
            url: Feed URL
            target_chat_id: 目标聊天ID
            feed_dir: Feed目录
            
        Returns:
            int: 发送的条目数量
        """
        try:
            # 获取pending数据
            pending_data = self.state_manager.get_pending_data(feed_dir)
            if not pending_data:
                logging.warning(f"无法读取pending数据: {url}")
                # 清理无效的pending状态
                self.state_manager.delete_pending_file(feed_dir)
                return 0
            
            entries = pending_data.get("entries", [])
            xml_content = pending_data.get("xml_content", "")
            
            if not entries:
                logging.warning(f"pending数据中没有条目: {url}")
                self.state_manager.delete_pending_file(feed_dir)
                return 0
            
            logging.info(f"重新发送pending内容: {url}, 条目数: {len(entries)}")
            
            # 发送通知
            send_success = await self._send_notification_safe(
                bot, url, entries, xml_content, target_chat_id
            )
            
            # 根据发送结果处理pending状态
            if send_success:
                self.state_manager.delete_pending_file(feed_dir)
                logging.info(f"pending内容发送成功: {url}")
                return len(entries)
            else:
                logging.warning(f"pending内容发送失败: {url}，保留pending状态")
                return 0
                
        except Exception as e:
            logging.error(f"处理pending Feed失败: {url}, 错误: {str(e)}")
            return 0
    
    async def _send_notification_safe(
        self, bot: Bot, url: str, entries: List, xml_content: str, target_chat_id: str
    ) -> bool:
        """
        安全地发送通知，捕获异常并返回发送结果
        
        Args:
            bot: Telegram Bot实例
            url: Feed URL
            entries: 条目列表
            xml_content: XML内容
            target_chat_id: 目标聊天ID
            
        Returns:
            bool: 是否发送成功
        """
        try:
            await send_update_notification(bot, url, entries, xml_content, target_chat_id)
            return True
        except Exception as e:
            logging.error(f"发送通知失败: {url}, 错误: {str(e)}")
            return False
    
    def cleanup_old_files(self) -> None:
        """清理过期的pending文件"""
        try:
            feeds = self.rss_manager.get_feeds()
            for url in feeds.keys():
                feed_dir = self.rss_manager._get_feed_dir(url)
                self.state_manager.cleanup_old_pending_files(feed_dir)
            logging.info("清理过期pending文件完成")
        except Exception as e:
            logging.error(f"清理过期文件失败: {str(e)}")


# 创建全局调度器实例
rss_scheduler = RSSScheduler()


# 导出函数供telegram_bot调用
async def run_scheduled_check(bot: Bot) -> None:
    """
    RSS定时检查入口函数
    
    Args:
        bot: Telegram Bot实例
    """
    await rss_scheduler.run_scheduled_check(bot) 