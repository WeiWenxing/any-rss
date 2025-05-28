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
from services.common.unified_scheduler import UnifiedScheduler


class RSSHubScheduler(UnifiedScheduler):
    """
    RSSHub定时任务调度器

    继承统一调度器基类，完全复用douyin模块的调度逻辑，为RSS订阅提供定时更新和发送功能
    """

    def __init__(self, data_dir: str = "storage/rsshub"):
        """
        初始化RSSHub调度器

        Args:
            data_dir: 数据存储目录
        """
        # 创建RSSHub管理器
        rsshub_manager = create_rsshub_manager(data_dir)

        # 调用父类构造函数
        super().__init__(module_name="rsshub", manager=rsshub_manager)

        # 初始化RSS特定组件
        self.rss_parser = create_rss_parser()
        self.rss_converter = create_rss_converter()

        # 调度配置（复用douyin的配置逻辑）
        self.check_interval = 3600  # 1小时检查一次
        self.max_concurrent_feeds = 5  # 最大并发RSS源数量
        self.max_items_per_batch = 20  # 每批最大条目数量

        self.logger.info(f"RSSHub调度器初始化完成，检查间隔: {self.check_interval}秒")

    # ==================== 重写UnifiedScheduler的可选方法 ====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于日志）

        Returns:
            str: 模块显示名称
        """
        return "RSSHUB"

    def should_skip_source(self, source_url: str) -> bool:
        """
        判断是否应该跳过某个RSS源（子类可重写）

        Args:
            source_url: RSS源URL

        Returns:
            bool: 是否跳过
        """
        # RSS源一般不需要跳过，除非有特殊需求
        return False

    async def cleanup_old_files(self) -> None:
        """
        清理过期文件（RSS特定的清理逻辑）
        """
        try:
            self.logger.info("开始RSSHub数据清理任务")

            # 清理孤立的数据
            cleaned_count = self.manager.cleanup_orphaned_data()

            # 清理过期的已知条目（保留最近10000个）
            removed_count = self.manager.cleanup_old_known_items(max_known_items=10000)

            self.logger.info(f"RSSHub数据清理完成，清理了 {cleaned_count} 个孤立数据项，{removed_count} 个过期条目")

        except Exception as e:
            self.logger.error(f"RSSHub数据清理失败: {str(e)}", exc_info=True)


# 便捷函数：创建RSSHub调度器实例
def create_rsshub_scheduler(data_dir: str = "storage/rsshub") -> RSSHubScheduler:
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
        stats = scheduler.get_scheduler_statistics()
        print(f"✅ 获取统计信息: {stats.get('total_sources', 0)} 个RSS源")

        # 测试数据清理
        await scheduler.cleanup_old_files()
        print("✅ 数据清理任务完成")

        print("🎉 RSSHub调度器模块测试完成")

    # 运行测试
    asyncio.run(test_rsshub_scheduler())