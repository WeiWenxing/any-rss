"""
RSSHub调度器模块

该模块负责RSSHub的定时任务调度，完全复用douyin模块的调度逻辑。
支持定时检查RSS更新、批量发送新内容、清理过期数据等功能。

主要功能：
1. 定时检查所有RSS源的更新
2. 批量发送新RSS内容到订阅频道
3. 智能去重和内容过滤
4. 发送间隔管理和错误处理
5. 数据清理和维护任务

作者: Assistant
创建时间: 2024年
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from telegram import Bot

from .manager import RSSHubManager, create_rsshub_manager
from .rss_parser import RSSParser, create_rss_parser
from .rss_converter import create_rss_converter
from .rss_entry import RSSEntry
from services.common.unified_sender import UnifiedTelegramSender
from services.common.unified_interval_manager import UnifiedIntervalManager


class RSSHubScheduler:
    """
    RSSHub定时任务调度器

    完全复用douyin模块的调度逻辑，为RSS订阅提供定时更新和发送功能
    """

    def __init__(self, data_dir: str = "data/rsshub"):
        """
        初始化RSSHub调度器

        Args:
            data_dir: 数据存储目录
        """
        self.logger = logging.getLogger(__name__)

        # 初始化核心组件
        self.rsshub_manager = create_rsshub_manager(data_dir)
        self.rss_parser = create_rss_parser()
        self.rss_converter = create_rss_converter()
        self.unified_sender = UnifiedTelegramSender()

        # 调度配置（复用douyin的配置逻辑）
        self.check_interval = 300  # 5分钟检查一次（与douyin保持一致）
        self.max_concurrent_feeds = 5  # 最大并发RSS源数量
        self.max_items_per_batch = 20  # 每批最大条目数量

        self.logger.info(f"RSSHub调度器初始化完成，检查间隔: {self.check_interval}秒")

    async def check_all_rss_updates(self, bot: Bot) -> Dict[str, Any]:
        """
        检查所有RSS源的更新（完全复用douyin的检查逻辑）

        Args:
            bot: Telegram Bot实例

        Returns:
            Dict[str, Any]: 检查结果统计
        """
        try:
            self.logger.info("开始检查所有RSS源更新")
            start_time = datetime.now()

            # 获取所有RSS源
            all_rss_urls = self.rsshub_manager.get_all_rss_urls()
            if not all_rss_urls:
                self.logger.info("没有RSS订阅，跳过检查")
                return {"total_feeds": 0, "updated_feeds": 0, "new_items": 0, "sent_items": 0}

            self.logger.info(f"开始检查 {len(all_rss_urls)} 个RSS源")

            # 统计信息
            stats = {
                "total_feeds": len(all_rss_urls),
                "updated_feeds": 0,
                "new_items": 0,
                "sent_items": 0,
                "errors": 0
            }

            # 分批处理RSS源（避免并发过多）
            for i in range(0, len(all_rss_urls), self.max_concurrent_feeds):
                batch_urls = all_rss_urls[i:i + self.max_concurrent_feeds]
                
                # 并发处理当前批次
                tasks = [
                    self._check_single_rss_update(bot, rss_url)
                    for rss_url in batch_urls
                ]

                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # 统计批次结果
                for result in batch_results:
                    if isinstance(result, Exception):
                        stats["errors"] += 1
                        self.logger.error(f"RSS检查任务异常: {str(result)}", exc_info=True)
                    elif isinstance(result, dict):
                        if result.get("has_updates"):
                            stats["updated_feeds"] += 1
                        stats["new_items"] += result.get("new_items", 0)
                        stats["sent_items"] += result.get("sent_items", 0)

            # 记录检查完成
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            self.logger.info(
                f"RSS更新检查完成: "
                f"总源数={stats['total_feeds']}, "
                f"有更新={stats['updated_feeds']}, "
                f"新条目={stats['new_items']}, "
                f"已发送={stats['sent_items']}, "
                f"错误={stats['errors']}, "
                f"耗时={duration:.2f}秒"
            )

            return stats

        except Exception as e:
            self.logger.error(f"检查RSS更新失败: {str(e)}", exc_info=True)
            return {"total_feeds": 0, "updated_feeds": 0, "new_items": 0, "sent_items": 0, "errors": 1}

    async def _check_single_rss_update(self, bot: Bot, rss_url: str) -> Dict[str, Any]:
        """
        检查单个RSS源的更新

        Args:
            bot: Telegram Bot实例
            rss_url: RSS源URL

        Returns:
            Dict[str, Any]: 检查结果
        """
        try:
            self.logger.debug(f"检查RSS源更新: {rss_url}")

            # 获取订阅频道
            target_channels = self.rsshub_manager.get_subscription_channels(rss_url)
            if not target_channels:
                self.logger.warning(f"RSS源无订阅频道: {rss_url}")
                return {"has_updates": False, "new_items": 0, "sent_items": 0}

            # 解析RSS内容
            try:
                entries = self.rss_parser.parse_feed(rss_url)
            except Exception as e:
                self.logger.error(f"解析RSS源失败: {rss_url}, 错误: {str(e)}", exc_info=True)
                return {"has_updates": False, "new_items": 0, "sent_items": 0}

            if not entries:
                self.logger.debug(f"RSS源无内容: {rss_url}")
                return {"has_updates": False, "new_items": 0, "sent_items": 0}

            # 过滤新内容（复用douyin的去重逻辑）
            new_entries = self._filter_new_entries(rss_url, entries)

            if not new_entries:
                self.logger.debug(f"RSS源无新内容: {rss_url}")
                return {"has_updates": False, "new_items": 0, "sent_items": 0}

            self.logger.info(f"RSS源发现新内容: {rss_url}, {len(new_entries)} 个新条目")

            # 批量发送新内容
            sent_count = await self._process_batch(bot, new_entries, rss_url, target_channels)

            return {
                "has_updates": True,
                "new_items": len(new_entries),
                "sent_items": sent_count
            }

        except Exception as e:
            self.logger.error(f"检查单个RSS源失败: {rss_url}, 错误: {str(e)}", exc_info=True)
            return {"has_updates": False, "new_items": 0, "sent_items": 0}

    def _filter_new_entries(self, rss_url: str, entries: List[RSSEntry]) -> List[RSSEntry]:
        """
        过滤新RSS条目（完全复用douyin的去重逻辑）

        Args:
            rss_url: RSS源URL
            entries: RSS条目列表

        Returns:
            List[RSSEntry]: 新条目列表
        """
        try:
            # 获取已知条目ID
            known_item_ids = set(self.rsshub_manager.get_known_item_ids(rss_url))

            # 过滤新条目
            new_entries = []
            for entry in entries:
                if entry.item_id not in known_item_ids:
                    new_entries.append(entry)

            # 限制批次大小（避免一次发送过多）
            if len(new_entries) > self.max_items_per_batch:
                self.logger.warning(f"RSS源新条目过多: {rss_url}, {len(new_entries)} 个，限制为 {self.max_items_per_batch} 个")
                # 按发布时间排序，取最新的条目
                sorted_entries = sorted(
                    new_entries, 
                    key=lambda x: x.effective_published_time or datetime.min, 
                    reverse=True
                )
                new_entries = sorted_entries[:self.max_items_per_batch]

            self.logger.debug(f"RSS源过滤结果: {rss_url}, {len(new_entries)} 个新条目")
            return new_entries

        except Exception as e:
            self.logger.error(f"过滤RSS新条目失败: {rss_url}, 错误: {str(e)}", exc_info=True)
            return []

    async def _process_batch(self, bot: Bot, new_entries: List[RSSEntry], rss_url: str, target_channels: List[str]) -> int:
        """
        处理批量RSS内容，使用统一的发送策略

        Args:
            bot: Telegram Bot实例
            new_entries: 新RSS条目列表
            rss_url: RSS源URL
            target_channels: 目标频道列表

        Returns:
            int: 发送成功的内容数量
        """
        try:
            # 初始化间隔管理器（批量发送场景）
            interval_manager = UnifiedIntervalManager("rsshub_send")

            # 按发布时间排序（从旧到新，确保时间顺序）
            sorted_entries = sorted(
                new_entries, 
                key=lambda x: x.effective_published_time or datetime.min, 
                reverse=False
            )

            sent_count = 0

            for entry in sorted_entries:
                try:
                    # 转换为统一消息格式
                    telegram_message = self.rss_converter.to_telegram_message(entry)

                    # 发送到所有订阅频道
                    entry_sent_count = 0
                    for chat_id in target_channels:
                        try:
                            # 发送消息
                            message_ids = await self.unified_sender.send_message(bot, chat_id, telegram_message)

                            if message_ids:
                                # 保存消息映射
                                self.rsshub_manager.save_message_mapping(rss_url, entry.item_id, chat_id, message_ids)
                                entry_sent_count += 1
                                self.logger.debug(f"RSS内容发送成功: {entry.item_id} -> {chat_id}")

                            # 应用发送间隔
                            await interval_manager.apply_interval()

                        except Exception as e:
                            self.logger.error(f"发送RSS内容到频道失败: {chat_id}, 条目: {entry.item_id}, 错误: {str(e)}", exc_info=True)
                            continue

                    # 如果至少发送到一个频道，标记为已知条目
                    if entry_sent_count > 0:
                        self.rsshub_manager.add_known_item_id(rss_url, entry.item_id)
                        sent_count += 1
                        self.logger.debug(f"RSS条目处理完成: {entry.item_id}, 发送到 {entry_sent_count} 个频道")

                except Exception as e:
                    self.logger.error(f"处理RSS条目失败: {entry.item_id}, 错误: {str(e)}", exc_info=True)
                    continue

            self.logger.info(f"RSS批量处理完成: {rss_url}, {sent_count}/{len(new_entries)} 个条目发送成功")
            return sent_count

        except Exception as e:
            self.logger.error(f"RSS批量处理失败: {rss_url}, 错误: {str(e)}", exc_info=True)
            return 0

    def cleanup_old_data(self) -> None:
        """
        清理过期的数据（复用douyin的清理逻辑）
        """
        try:
            self.logger.info("开始RSS数据清理任务")

            # 清理孤立的数据
            cleaned_count = self.rsshub_manager.cleanup_orphaned_data()

            # 清理过期的已知条目（保留最近1000个）
            self._cleanup_old_known_items()

            self.logger.info(f"RSS数据清理完成，清理了 {cleaned_count} 个孤立数据项")

        except Exception as e:
            self.logger.error(f"RSS数据清理失败: {str(e)}", exc_info=True)

    def _cleanup_old_known_items(self) -> None:
        """
        清理过期的已知条目ID（保留最近的条目）
        """
        try:
            all_rss_urls = self.rsshub_manager.get_all_rss_urls()
            max_known_items = 1000  # 每个RSS源最多保留1000个已知条目

            for rss_url in all_rss_urls:
                try:
                    known_item_ids = self.rsshub_manager.get_known_item_ids(rss_url)
                    
                    if len(known_item_ids) > max_known_items:
                        # 保留最新的条目（简单的FIFO策略）
                        trimmed_ids = known_item_ids[-max_known_items:]
                        self.rsshub_manager.save_known_item_ids(rss_url, trimmed_ids)
                        
                        removed_count = len(known_item_ids) - len(trimmed_ids)
                        self.logger.info(f"清理RSS源过期条目: {rss_url}, 移除 {removed_count} 个旧条目")

                except Exception as e:
                    self.logger.warning(f"清理RSS源已知条目失败: {rss_url}, 错误: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"清理已知条目失败: {str(e)}", exc_info=True)

    def get_scheduler_stats(self) -> Dict[str, Any]:
        """
        获取调度器统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            # 获取管理器统计信息
            manager_stats = self.rsshub_manager.get_statistics()

            # 添加调度器特定信息
            scheduler_stats = {
                "check_interval": self.check_interval,
                "max_concurrent_feeds": self.max_concurrent_feeds,
                "max_items_per_batch": self.max_items_per_batch,
                "last_check_time": datetime.now().isoformat()
            }

            # 合并统计信息
            return {**manager_stats, **scheduler_stats}

        except Exception as e:
            self.logger.error(f"获取调度器统计信息失败: {str(e)}", exc_info=True)
            return {}


# 便捷函数：创建RSSHub调度器实例
def create_rsshub_scheduler(data_dir: str = "data/rsshub") -> RSSHubScheduler:
    """
    创建RSSHub调度器实例

    Args:
        data_dir: 数据存储目录

    Returns:
        RSSHubScheduler: RSSHub调度器实例
    """
    return RSSHubScheduler(data_dir)


if __name__ == "__main__":
    # 模块测试代码
    import asyncio

    async def test_rsshub_scheduler():
        """测试RSSHub调度器功能"""
        print("🧪 RSSHub调度器模块测试")

        # 创建调度器
        scheduler = create_rsshub_scheduler("test_data/rsshub")
        print(f"✅ 创建RSSHub调度器: {type(scheduler).__name__}")

        # 测试统计信息
        stats = scheduler.get_scheduler_stats()
        print(f"✅ 获取统计信息: {stats.get('total_rss_sources', 0)} 个RSS源")

        # 测试数据清理
        scheduler.cleanup_old_data()
        print("✅ 数据清理任务完成")

        print("🎉 RSSHub调度器模块测试完成")

    # 运行测试
    asyncio.run(test_rsshub_scheduler()) 