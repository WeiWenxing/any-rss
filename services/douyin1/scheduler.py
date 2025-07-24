"""
Douyin1调度器模块

该模块负责Douyin1的定时任务调度，完全复用unified_scheduler模块的调度逻辑。
支持定时检查抖音更新、批量发送新内容、清理过期数据等功能。

主要功能：
1. 定时检查所有抖音账号的更新
2. 批量发送新抖音内容到订阅频道
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

from .manager import ContentManager, create_content_manager
from . import MODULE_NAME, MODULE_DISPLAY_NAME, DATA_DIR_PREFIX
from services.common.unified_scheduler import UnifiedScheduler


class Douyin1Scheduler(UnifiedScheduler):
    """
    Douyin1定时任务调度器

    继承统一调度器基类，完全复用unified_scheduler模块的调度逻辑，为抖音订阅提供定时更新和发送功能
    """

    def __init__(self, data_dir: str = None):
        """
        初始化Douyin1调度器

        Args:
            data_dir: 数据存储目录
        """
        # 使用模块默认配置
        if data_dir is None:
            data_dir = DATA_DIR_PREFIX

        # 创建Douyin1管理器
        douyin1_manager = create_content_manager(data_dir)

        # 调用父类构造函数
        super().__init__(module_name=MODULE_NAME, manager=douyin1_manager)

        # 调度配置
        self.check_interval = 1800  # 30分钟检查一次

        self.logger.info(f"Douyin1调度器初始化完成，检查间隔: {self.check_interval}秒")

    # ==================== 重写UnifiedScheduler的可选方法 ====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于日志）

        Returns:
            str: 模块显示名称
        """
        return "DOUYIN1"

    def should_skip_source(self, source_url: str) -> bool:
        """
        判断是否应该跳过某个抖音源（子类可重写）

        Args:
            source_url: 抖音账号URL

        Returns:
            bool: 是否跳过
        """
        # 抖音源一般不需要跳过，除非有特殊需求
        return False

    async def cleanup_old_files(self) -> None:
        """
        清理过期文件（Douyin1特定的清理逻辑）
        """
        try:
            self.logger.info("开始Douyin1数据清理任务")

            # 清理过期的已知条目（保留最近5000个）
            removed_count = self.manager.cleanup_old_known_items(max_known_items=5000)

            self.logger.info(f"Douyin1数据清理完成，清理了 {removed_count} 个过期条目")

        except Exception as e:
            self.logger.error(f"Douyin1数据清理失败: {str(e)}", exc_info=True)


# 便捷函数：创建Douyin1调度器实例
def create_douyin1_scheduler(data_dir: str = None) -> Douyin1Scheduler:
    """
    创建Douyin1调度器实例

    Args:
        data_dir: 数据存储目录

    Returns:
        Douyin1Scheduler: Douyin1调度器实例
    """
    return Douyin1Scheduler(data_dir)


# 创建全局调度器实例
douyin1_scheduler = Douyin1Scheduler()


# 导出函数供telegram_bot调用
async def run_scheduled_check(bot: Bot) -> None:
    """
    Douyin1定时检查入口函数

    Args:
        bot: Telegram Bot实例
    """
    await douyin1_scheduler.run_scheduled_check(bot)


if __name__ == "__main__":
    # 模块测试代码
    import asyncio

    async def test_douyin1_scheduler():
        """测试Douyin1调度器功能 - 使用真实数据但不处理URL"""
        print("🧪 Douyin1调度器模块测试")
        print("=" * 80)

        # 创建调度器 - 使用真实数据目录
        scheduler = douyin1_scheduler
        print(f"✅ 创建Douyin1调度器: {type(scheduler).__name__}")
        print(f"📂 数据目录: storage/douyin1")
        print()

        # 获取真实订阅数据
        try:
            subscriptions = scheduler.manager.get_subscriptions()
            print(f"✅ 获取真实订阅数据: {len(subscriptions)} 个订阅源")

            if subscriptions:
                print("\n📋 订阅详情列表:")
                print("=" * 80)

                total_channels = 0
                for i, (source_url, target_channels) in enumerate(subscriptions.items(), 1):
                    print(f"📌 订阅 #{i}")
                    print(f"   🔗 抖音URL: {source_url}")

                    # 处理频道显示
                    if isinstance(target_channels, list):
                        channels_str = ', '.join(target_channels)
                        channel_count = len(target_channels)
                    else:
                        # 兼容旧格式
                        channels_str = str(target_channels)
                        channel_count = 1

                    print(f"   📺 目标频道: {channels_str}")
                    print(f"   📊 频道数量: {channel_count} 个")
                    total_channels += channel_count

                    # 获取已知内容统计
                    try:
                        known_items = scheduler.manager.get_known_item_ids(source_url)
                        print(f"   📦 已知内容: {len(known_items)} 个")
                    except Exception as e:
                        print(f"   📦 已知内容: 无法获取 - {str(e)}")

                    print()

                print("=" * 80)
                print(f"📊 总体统计:")
                print(f"   📈 订阅源总数: {len(subscriptions)} 个")
                print(f"   📺 频道总数: {total_channels} 个")
                print(f"   📋 平均每源频道数: {total_channels / len(subscriptions):.1f} 个")

            else:
                print("📋 当前没有订阅数据")
                print("💡 提示: 可能数据在服务器上，本地为空")

        except Exception as e:
            print(f"❌ 获取订阅数据失败: {str(e)}")
            import traceback
            traceback.print_exc()

        print()

        # 测试调度器统计信息
        try:
            stats = scheduler.get_scheduler_statistics()
            print(f"✅ 调度器统计信息:")
            for key, value in stats.items():
                print(f"   📊 {key}: {value}")
        except Exception as e:
            print(f"❌ 获取统计信息失败: {str(e)}")

        print()

        # 测试数据清理功能
        try:
            print("🧹 开始数据清理任务...")
            await scheduler.cleanup_old_files()
            print("✅ 数据清理任务完成")
        except Exception as e:
            print(f"❌ 数据清理失败: {str(e)}")
            import traceback
            traceback.print_exc()

        print()
        print("🎉 Douyin1调度器模块测试完成")
        print("=" * 80)
        print("📝 测试说明:")
        print("   - 使用真实数据目录 storage/douyin1")
        print("   - 仅读取和显示订阅信息")
        print("   - 不实际处理抖音URL")
        print("   - 不发送实际请求")

    # 运行测试
    asyncio.run(test_douyin1_scheduler())