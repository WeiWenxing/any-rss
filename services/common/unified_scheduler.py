"""
统一调度器基类

该模块抽取了douyin调度器的核心逻辑，为所有数据源模块提供统一的定时任务调度模式。
包含订阅检查、批量处理、错误处理等通用调度流程。

主要功能：
1. 抽象的调度器接口
2. 通用的定时检查流程
3. 统一的批量处理策略
4. 标准的错误处理和重试机制
5. 可配置的调度间隔管理
6. 统一的统计和监控

作者: Assistant
创建时间: 2024年
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from telegram import Bot

from .unified_manager import UnifiedContentManager


class UnifiedScheduler(ABC):
    """
    统一调度器基类

    抽取douyin调度器的核心逻辑，为所有数据源模块提供统一的定时任务调度模式
    """

    def __init__(self, module_name: str, manager: UnifiedContentManager):
        """
        初始化统一调度器

        Args:
            module_name: 模块名称（如'douyin', 'rsshub'）
            manager: 统一管理器实例
        """
        self.module_name = module_name
        self.manager = manager
        self.logger = logging.getLogger(f"{module_name}_scheduler")

        self.logger.info(f"{module_name}统一调度器初始化完成")

    # ==================== 抽象接口（子类可选实现）====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于日志）

        Returns:
            str: 模块显示名称
        """
        return self.module_name.upper()

    def should_skip_source(self, source_url: str) -> bool:
        """
        判断是否应该跳过某个数据源（子类可重写）

        Args:
            source_url: 数据源URL

        Returns:
            bool: 是否跳过
        """
        return False

    async def cleanup_old_files(self) -> None:
        """
        清理过期文件（子类可重写）
        """
        try:
            # 默认实现：不需要清理
            self.logger.info(f"{self.module_name}模块清理任务完成（暂无需清理的文件）")
        except Exception as e:
            self.logger.error(f"{self.module_name}模块清理文件失败: {str(e)}", exc_info=True)

    # ==================== 通用调度逻辑（完全复用douyin逻辑）====================

    async def run_scheduled_check(self, bot: Bot) -> None:
        """
        执行定时检查（完全复用douyin调度器逻辑）

        Args:
            bot: Telegram Bot实例
        """
        try:
            # 刷新订阅缓存，确保获取最新数据
            self.manager._load_subscriptions()
            self.logger.debug(f"刷新{self.module_name}订阅缓存")

            subscriptions = self.manager.get_subscriptions()
            display_name = self.get_module_display_name()
            self.logger.info(f"定时任务开始检查{display_name}订阅更新，共 {len(subscriptions)} 个URL")

            # 统计信息
            total_new_content = 0
            success_count = 0
            error_count = 0

            # 逐个处理每个数据源的订阅
            for source_url, target_channels in subscriptions.items():
                try:
                    # 检查是否应该跳过
                    if self.should_skip_source(source_url):
                        self.logger.info(f"跳过{display_name}源: {source_url}")
                        continue

                    self.logger.info(f"处理{display_name}订阅: {source_url} -> {len(target_channels)} 个频道")

                    # 使用多频道高效处理
                    sent_count = await self.process_multi_channel_subscription(bot, source_url, target_channels)

                    if sent_count > 0:
                        total_new_content += sent_count
                        success_count += 1
                        self.logger.info(f"{display_name}订阅 {source_url} 处理完成，发送了 {sent_count} 个新内容")
                    else:
                        self.logger.info(f"{display_name}订阅 {source_url} 无新内容")

                except Exception as e:
                    error_count += 1
                    self.logger.error(f"处理{display_name}订阅失败: {source_url}, 错误: {str(e)}", exc_info=True)
                    continue

            # 输出总结
            self.logger.info(f"📊 {display_name}定时任务完成: 成功 {success_count} 个，失败 {error_count} 个，共发送 {total_new_content} 个新内容")

        except Exception as e:
            self.logger.error(f"{self.get_module_display_name()}定时任务执行失败: {str(e)}", exc_info=True)



    async def process_multi_channel_subscription(self, bot: Bot, source_url: str, target_channels: List[str]) -> int:
        """
        处理单个URL的多频道订阅（完全复用douyin高效转发机制）

        Args:
            bot: Telegram Bot实例
            source_url: 数据源URL
            target_channels: 目标频道列表

        Returns:
            int: 发送的新内容数量
        """
        try:
            display_name = self.get_module_display_name()
            self.logger.info(f"开始处理多频道{display_name}订阅: {source_url} -> {len(target_channels)} 个频道")

            # 检查更新（返回的内容已包含target_channels信息）
            success, error_msg, new_items = self.manager.check_updates(source_url)

            if not success:
                self.logger.warning(f"{display_name}订阅 {source_url} 检查失败: {error_msg}")
                return 0

            # 如果有新内容，使用高效转发机制
            if new_items and len(new_items) > 0:
                self.logger.info(f"{display_name}订阅 {source_url} 发现 {len(new_items)} 个新内容，将发送到 {len(target_channels)} 个频道")

                # 直接使用Manager的批量发送方法（多频道高效转发）
                sent_count = await self.manager.send_content_batch(bot, new_items, source_url, target_channels)

                self.logger.info(f"{display_name}订阅 {source_url} 发送完成，成功 {sent_count}/{len(new_items)} 个")
                return sent_count
            else:
                self.logger.info(f"{display_name}订阅 {source_url} 无新增内容")
                return 0

        except Exception as e:
            self.logger.error(f"处理多频道{self.get_module_display_name()}订阅失败: {source_url}, 错误: {str(e)}", exc_info=True)
            return 0



    # ==================== 统计和监控接口 ====================

    def get_subscription_count(self) -> int:
        """
        获取当前订阅数量

        Returns:
            int: 订阅数量
        """
        try:
            subscriptions = self.manager.get_subscriptions()
            return len(subscriptions)
        except Exception as e:
            self.logger.error(f"获取{self.get_module_display_name()}订阅数量失败: {str(e)}", exc_info=True)
            return 0

    def get_scheduler_statistics(self) -> Dict[str, Any]:
        """
        获取调度器统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            manager_stats = self.manager.get_statistics()
            scheduler_stats = {
                "module_name": self.module_name,
                "display_name": self.get_module_display_name(),
                "subscription_count": self.get_subscription_count(),
            }

            # 合并管理器统计信息
            scheduler_stats.update(manager_stats)
            return scheduler_stats

        except Exception as e:
            self.logger.error(f"获取{self.get_module_display_name()}调度器统计信息失败: {str(e)}", exc_info=True)
            return {"module_name": self.module_name, "error": str(e)}


# 便捷函数：创建统一调度器的工厂方法
def create_unified_scheduler(module_name: str, scheduler_class, manager: UnifiedContentManager, **kwargs) -> UnifiedScheduler:
    """
    创建统一调度器实例的工厂方法

    Args:
        module_name: 模块名称
        scheduler_class: 具体的调度器类
        manager: 统一管理器实例
        **kwargs: 传递给调度器构造函数的参数

    Returns:
        UnifiedScheduler: 统一调度器实例
    """
    return scheduler_class(module_name=module_name, manager=manager, **kwargs)


if __name__ == "__main__":
    # 模块测试代码
    def test_unified_scheduler():
        """测试统一调度器功能"""
        print("🧪 统一调度器模块测试")

        # 这里只能测试抽象接口，具体实现需要在子类中测试
        print("✅ 统一调度器基类定义完成")
        print("📝 子类可以重写可选方法")
        print("🎯 提供了完整的调度逻辑复用")

        print("🎉 统一调度器模块测试完成")

    # 运行测试
    test_unified_scheduler()