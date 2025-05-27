"""
统一对齐器模块

该模块提供跨模块的统一历史内容对齐功能，复用douyin模块的成熟对齐逻辑。
支持新频道订阅时的智能历史内容同步，确保所有频道内容的完整性和一致性。

主要功能：
1. 新频道历史内容对齐
2. 智能转发源选择
3. 批量复制控制
4. 转发失败时的降级策略
5. 跨模块通用接口

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple, Union
from telegram import Bot, Message
from telegram.error import TelegramError

from .unified_interval_manager import create_unified_interval_manager

from .unified_sender import UnifiedTelegramSender, create_unified_sender
from .telegram_message import TelegramMessage


class UnifiedAlignment:
    """
    统一对齐器

    提供跨模块的历史内容对齐功能，复用douyin模块的智能对齐策略。
    支持新频道订阅时从已有频道快速同步历史内容。
    """

    def __init__(self, sender: Optional[UnifiedTelegramSender] = None):
        """
        初始化统一对齐器

        Args:
            sender: 统一发送器实例，如果不提供则自动创建（使用alignment场景）
        """
        self.logger = logging.getLogger(__name__)
        self.sender = sender or create_unified_sender("alignment")  # 使用对齐场景的间隔配置
        self.interval_manager = create_unified_interval_manager("alignment")

    async def perform_historical_alignment(
        self,
        bot: Bot,
        source_url: str,
        target_chat_id: str,
        manager: Any,
        content_items: Optional[List[Any]] = None
    ) -> Tuple[bool, str, int]:
        """
        执行历史内容对齐

        这是所有模块的统一对齐入口，复用douyin模块的对齐逻辑。

        Args:
            bot: Telegram Bot实例
            source_url: 数据源URL（douyin_url、rss_url等）
            target_chat_id: 目标频道ID
            manager: 模块管理器实例（提供数据访问接口）
            content_items: 可选的内容项列表，如果不提供则从manager获取

        Returns:
            Tuple[bool, str, int]: (成功状态, 错误信息, 对齐数量)
        """
        try:
            self.logger.info(f"开始执行历史对齐: {source_url} -> {target_chat_id}")

            # 1. 获取已知内容ID列表
            if content_items is None:
                known_item_ids = manager.get_known_item_ids(source_url)
                self.logger.info(f"从管理器获取到 {len(known_item_ids)} 个已知内容ID")
            else:
                known_item_ids = [getattr(item, 'item_id', str(item)) for item in content_items]
                self.logger.info(f"使用提供的 {len(known_item_ids)} 个内容项")

            if not known_item_ids:
                return True, "没有历史内容需要对齐", 0

            # 2. 执行批量对齐（使用douyin模块的逻辑）
            aligned_count = await self._perform_batch_alignment(
                bot, source_url, target_chat_id, known_item_ids, manager
            )

            self.logger.info(f"历史对齐完成: 成功对齐 {aligned_count} 个内容")
            return True, f"成功对齐 {aligned_count} 个历史内容", aligned_count

        except Exception as e:
            error_msg = f"历史对齐失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg, 0

    def _get_all_available_sources(
        self,
        source_url: str,
        item_id: str,
        manager: Any
    ) -> List[Tuple[str, List[int]]]:
        """
        获取所有可用的转发源（完全复用douyin模块逻辑）

        这个方法直接调用manager的get_all_available_message_sources方法，
        与douyin模块保持完全一致的转发源获取逻辑。

        Args:
            source_url: 数据源URL
            item_id: 内容项ID
            manager: 模块管理器实例

        Returns:
            List[Tuple[str, List[int]]]: 所有可用的转发源列表 [(频道ID, 消息ID列表), ...]
        """
        try:
            # 直接调用manager的方法，与douyin模块保持一致
            # 所有模块的manager都必须实现这个方法
            available_sources = manager.get_all_available_message_sources(source_url, item_id)
            self.logger.debug(f"获取到 {len(available_sources)} 个可用转发源: {item_id}")
            return available_sources

        except Exception as e:
            self.logger.error(f"获取所有可用转发源失败: {str(e)}", exc_info=True)
            return []



    async def _perform_batch_alignment(
        self,
        bot: Bot,
        source_url: str,
        target_chat_id: str,
        known_item_ids: List[str],
        manager: Any
    ) -> int:
        """
        执行批量对齐操作（完全复用douyin模块逻辑）

        使用与douyin模块完全相同的对齐策略：
        1. 获取所有可用的转发源
        2. 依次尝试每个转发源，直到成功
        3. 所有转发源都失败才跳过该内容

        Args:
            bot: Telegram Bot实例
            source_url: 数据源URL
            target_chat_id: 目标频道ID
            known_item_ids: 已知内容ID列表
            manager: 模块管理器实例

        Returns:
            int: 成功对齐的内容数量
        """
        aligned_count = 0
        total_items = len(known_item_ids)

        self.logger.info(f"开始批量对齐: {total_items} 个内容项")

        # 按时间顺序处理（假设item_id包含时间信息或使用索引顺序）
        for index, item_id in enumerate(known_item_ids, 1):
            item_success = False

            try:
                # 检查目标频道是否已有此内容
                message_mapping = manager.get_message_mapping(source_url, item_id)
                target_message_ids = message_mapping.get(target_chat_id, [])
                if target_message_ids:
                    self.logger.debug(f"跳过内容 {item_id}: 目标频道已存在")
                    aligned_count += 1  # 计为已对齐
                    continue

                # 获取所有可用的转发源（复用douyin模块逻辑）
                all_available_sources = self._get_all_available_sources(source_url, item_id, manager)
                if not all_available_sources:
                    self.logger.warning(f"历史对齐: 内容 {item_id} 没有可用的转发源，跳过 ({index}/{total_items})")
                    continue

                # 遍历所有可用源，直到成功（复用douyin模块逻辑）
                for source_channel, source_message_ids in all_available_sources:
                    # 跳过目标频道（不能从自己转发给自己）
                    if source_channel == target_chat_id:
                        continue

                    try:
                        # 复制整个消息组到新频道（不显示转发源）
                        copied_messages = await self.sender.copy_messages(
                            bot, source_channel, target_chat_id, source_message_ids
                        )

                        if copied_messages:
                            # 保存复制后的所有消息ID
                            copied_message_ids = [msg.message_id for msg in copied_messages]
                            manager.save_message_mapping(
                                source_url, item_id, target_chat_id, copied_message_ids
                            )

                            self.logger.info(f"历史对齐成功 ({index}/{total_items}): {item_id} 从 {source_channel} 复制到 {target_chat_id}, 消息ID列表: {copied_message_ids}")
                            item_success = True
                            break  # 成功后跳出源循环，处理下一个内容

                    except Exception as e:
                        self.logger.warning(f"历史对齐复制失败 ({index}/{total_items}): {item_id} 从 {source_channel} 复制失败: {str(e)}")
                        continue  # 尝试下一个转发源

                # 统计成功的内容
                if item_success:
                    aligned_count += 1
                else:
                    self.logger.error(f"历史对齐失败 ({index}/{total_items}): {item_id} 所有转发源都失败，该内容无法对齐")

                # 使用间隔管理器控制对齐间隔（复用douyin模块逻辑）
                if index < total_items:
                    await self.interval_manager.wait_before_send(
                        content_index=index,
                        total_content=total_items,
                        recent_error_rate=self.interval_manager.get_recent_error_rate()
                    )

            except Exception as e:
                self.logger.error(f"对齐内容 {item_id} 失败: {str(e)}", exc_info=True)
                continue

        return aligned_count



    def get_alignment_status(
        self,
        source_url: str,
        target_chat_id: str,
        manager: Any
    ) -> Dict[str, Any]:
        """
        获取对齐状态信息

        Args:
            source_url: 数据源URL
            target_chat_id: 目标频道ID
            manager: 模块管理器实例

        Returns:
            Dict[str, Any]: 对齐状态信息
        """
        try:
            known_item_ids = manager.get_known_item_ids(source_url)
            total_items = len(known_item_ids)

            aligned_items = 0
            missing_items = []

            for item_id in known_item_ids:
                message_mapping = manager.get_message_mapping(source_url, item_id)
                if target_chat_id in message_mapping and message_mapping[target_chat_id]:
                    aligned_items += 1
                else:
                    missing_items.append(item_id)

            alignment_rate = (aligned_items / total_items * 100) if total_items > 0 else 100

            return {
                'total_items': total_items,
                'aligned_items': aligned_items,
                'missing_items': len(missing_items),
                'alignment_rate': round(alignment_rate, 2),
                'missing_item_ids': missing_items[:10],  # 只返回前10个缺失项
                'is_fully_aligned': len(missing_items) == 0
            }

        except Exception as e:
            self.logger.error(f"获取对齐状态失败: {str(e)}", exc_info=True)
            return {
                'total_items': 0,
                'aligned_items': 0,
                'missing_items': 0,
                'alignment_rate': 0,
                'missing_item_ids': [],
                'is_fully_aligned': False,
                'error': str(e)
            }


# 便捷函数：创建统一对齐器实例
def create_unified_alignment(sender: Optional[UnifiedTelegramSender] = None) -> UnifiedAlignment:
    """
    创建统一对齐器实例

    Args:
        sender: 可选的统一发送器实例

    Returns:
        UnifiedAlignment: 统一对齐器实例
    """
    return UnifiedAlignment(sender)


# 便捷函数：快速执行历史对齐
async def perform_quick_alignment(
    bot: Bot,
    source_url: str,
    target_chat_id: str,
    manager: Any,
    content_items: Optional[List[Any]] = None
) -> Tuple[bool, str, int]:
    """
    快速执行历史对齐的便捷函数

    Args:
        bot: Telegram Bot实例
        source_url: 数据源URL
        target_chat_id: 目标频道ID
        manager: 模块管理器实例
        content_items: 可选的内容项列表

    Returns:
        Tuple[bool, str, int]: (成功状态, 错误信息, 对齐数量)
    """
    alignment = create_unified_alignment()
    return await alignment.perform_historical_alignment(
        bot, source_url, target_chat_id, manager, content_items
    )


if __name__ == "__main__":
    # 模块测试代码
    import asyncio

    async def test_unified_alignment():
        """测试统一对齐器功能"""
        print("🧪 统一对齐器模块测试")

        # 测试创建对齐器
        alignment = create_unified_alignment()
        print(f"✅ 创建统一对齐器: {type(alignment).__name__}")

        # 测试模拟管理器
        class MockManager:
            def get_known_item_ids(self, source_url):
                return ['item1', 'item2', 'item3']

            def get_subscription_channels(self, source_url):
                return ['@channel1', '@channel2']

            def get_message_mapping(self, source_url, item_id):
                return {'@channel1': [123, 124], '@channel2': []}

            def get_all_available_message_sources(self, source_url, item_id):
                return [('@channel1', [123, 124])]

        mock_manager = MockManager()

        # 测试获取所有可用转发源
        sources = alignment._get_all_available_sources(
            'test_url', 'item1', mock_manager
        )
        print(f"✅ 获取所有可用转发源: {len(sources)} 个")

        # 测试对齐状态
        status = alignment.get_alignment_status(
            'test_url', '@new_channel', mock_manager
        )
        print(f"✅ 对齐状态: {status['alignment_rate']}%")

        print("🎉 统一对齐器模块测试完成")

    # 运行测试
    asyncio.run(test_unified_alignment())