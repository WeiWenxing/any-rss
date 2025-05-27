"""
统一业务管理器基类

该模块抽取了douyin模块的核心业务逻辑，为所有数据源模块提供统一的业务处理模式。
包含订阅管理、内容检查、批量发送、历史对齐等通用业务流程。

主要功能：
1. 抽象的订阅管理接口
2. 通用的内容更新检查流程
3. 统一的批量发送算法（多频道高效转发）
4. 标准的已发送标记逻辑
5. 可配置的间隔管理集成
6. 统一的错误处理和日志记录

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple, Union
from telegram import Bot, Message

from .unified_interval_manager import UnifiedIntervalManager
from .unified_sender import UnifiedTelegramSender
from .telegram_message import TelegramMessage
from .message_converter import MessageConverter, get_converter


class UnifiedContentManager(ABC):
    """
    统一内容管理器基类

    抽取douyin模块的核心业务逻辑，为所有数据源模块提供统一的业务处理模式
    """

    def __init__(self, module_name: str, data_dir: str = None):
        """
        初始化统一管理器

        Args:
            module_name: 模块名称（如'douyin', 'rsshub'）
            data_dir: 数据存储目录（可选）
        """
        self.module_name = module_name
        self.logger = logging.getLogger(f"{module_name}_manager")
        
        # 初始化统一组件
        self.sender = UnifiedTelegramSender()
        self.interval_manager = UnifiedIntervalManager("batch_send")
        
        self.logger.info(f"{module_name}统一管理器初始化完成")

    # ==================== 抽象接口（子类必须实现）====================

    @abstractmethod
    def get_subscriptions(self) -> Dict[str, List[str]]:
        """
        获取所有订阅信息

        Returns:
            Dict[str, List[str]]: {源URL: [频道ID列表]}
        """
        pass

    @abstractmethod
    def get_subscription_channels(self, source_url: str) -> List[str]:
        """
        获取指定源的订阅频道列表

        Args:
            source_url: 数据源URL

        Returns:
            List[str]: 频道ID列表
        """
        pass

    @abstractmethod
    def fetch_latest_content(self, source_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取指定源的最新内容

        Args:
            source_url: 数据源URL

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 内容数据列表)
        """
        pass

    @abstractmethod
    def get_known_item_ids(self, source_url: str) -> List[str]:
        """
        获取已知的内容ID列表

        Args:
            source_url: 数据源URL

        Returns:
            List[str]: 已知内容ID列表
        """
        pass

    @abstractmethod
    def save_known_item_ids(self, source_url: str, item_ids: List[str]):
        """
        保存已知的内容ID列表

        Args:
            source_url: 数据源URL
            item_ids: 内容ID列表
        """
        pass

    @abstractmethod
    def generate_content_id(self, content_data: Dict) -> str:
        """
        生成内容的唯一标识

        Args:
            content_data: 内容数据

        Returns:
            str: 唯一标识
        """
        pass

    @abstractmethod
    def save_message_mapping(self, source_url: str, item_id: str, chat_id: str, message_ids: List[int]):
        """
        保存消息ID映射

        Args:
            source_url: 数据源URL
            item_id: 内容ID
            chat_id: 频道ID
            message_ids: 消息ID列表
        """
        pass

    @abstractmethod
    def get_all_available_message_sources(self, source_url: str, item_id: str) -> List[Tuple[str, List[int]]]:
        """
        获取所有可用的消息转发源

        Args:
            source_url: 数据源URL
            item_id: 内容ID

        Returns:
            List[Tuple[str, List[int]]]: 所有可用的转发源列表 [(频道ID, 消息ID列表), ...]
        """
        pass

    # ==================== 通用业务逻辑（完全复用douyin逻辑）====================

    def check_updates(self, source_url: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        检查指定数据源的更新（完全复用douyin模块逻辑）

        Args:
            source_url: 数据源URL

        Returns:
            Tuple[bool, str, Optional[List[Dict]]]: (是否成功, 错误信息, 新内容数据列表)
        """
        try:
            self.logger.info(f"检查{self.module_name}更新: {source_url}")

            # 获取订阅信息
            subscriptions = self.get_subscriptions()
            if source_url not in subscriptions:
                return False, "订阅不存在", None

            # 获取订阅的频道列表
            subscribed_channels = subscriptions[source_url]
            if not subscribed_channels:
                return False, "该URL没有订阅频道", None

            # 获取当前全部内容
            success, error_msg, all_content_data = self.fetch_latest_content(source_url)
            if not success:
                return False, error_msg, None

            if not all_content_data or len(all_content_data) == 0:
                return False, "获取到的内容数据为空", None

            # 获取已知的item IDs（全局已发送的）
            known_item_ids = self.get_known_item_ids(source_url)

            # 找出新的items
            new_items = []

            for content_data in all_content_data:
                item_id = self.generate_content_id(content_data)

                # 如果这个item ID不在已知列表中，说明是新的
                if item_id not in known_item_ids:
                    # 添加item_id和频道信息到内容中，用于后续发送
                    content_data["item_id"] = item_id
                    content_data["target_channels"] = subscribed_channels.copy()
                    new_items.append(content_data)
                    self.logger.info(f"发现新内容: {content_data.get('title', '无标题')} (ID: {item_id}) -> 频道: {subscribed_channels}")

            if new_items:
                self.logger.info(f"发现 {len(new_items)} 个新内容，将发送到 {len(subscribed_channels)} 个频道")
                return True, f"发现 {len(new_items)} 个新内容", new_items
            else:
                self.logger.info(f"无新内容: {source_url}")
                return True, "无新内容", None

        except Exception as e:
            self.logger.error(f"检查{self.module_name}更新失败: {source_url}", exc_info=True)
            return False, f"检查失败: {str(e)}", None

    def mark_item_as_sent(self, source_url: str, content_data: Dict) -> bool:
        """
        标记某个item为已成功发送（完全复用douyin模块逻辑）

        Args:
            source_url: 数据源URL
            content_data: 内容数据

        Returns:
            bool: 是否标记成功
        """
        try:
            item_id = self.generate_content_id(content_data)
            known_item_ids = self.get_known_item_ids(source_url)

            # 如果不在已知列表中，添加进去
            if item_id not in known_item_ids:
                known_item_ids.append(item_id)
                self.save_known_item_ids(source_url, known_item_ids)
                self.logger.info(f"标记item为已发送: {content_data.get('title', '无标题')} (ID: {item_id})")
                return True
            else:
                self.logger.debug(f"item已在已知列表中: {item_id}")
                return True

        except Exception as e:
            self.logger.error(f"标记item为已发送失败: {source_url}, 错误: {str(e)}", exc_info=True)
            return False

    async def send_content_batch(self, bot: Bot, content_items: List[Dict], source_url: str, target_channels: List[str]) -> int:
        """
        批量发送内容到多个频道（完全复用douyin的多频道高效转发算法）

        Args:
            bot: Telegram Bot实例
            content_items: 要发送的内容列表
            source_url: 数据源URL
            target_channels: 目标频道列表

        Returns:
            int: 成功发送的内容数量
        """
        self.logger.info(f"开始批量发送 {len(content_items)} 个内容到 {len(target_channels)} 个频道")

        # 重新初始化间隔管理器为批量发送场景
        self.interval_manager = UnifiedIntervalManager("batch_send")
        sent_count = 0

        # 按时间排序（从旧到新）
        sorted_items = self._sort_content_by_time(content_items)

        for i, content in enumerate(sorted_items):
            # 为当前内容项维护成功记录（内存中）
            successful_channels = {}  # {channel_id: [message_id1, message_id2, ...]}

            try:
                # 发送前等待（使用配置化间隔管理器）
                await self.interval_manager.wait_before_send(
                    content_index=i,
                    total_content=len(sorted_items),
                    recent_error_rate=self.interval_manager.get_recent_error_rate()
                )

                # 确保content有item_id字段
                if 'item_id' not in content:
                    content['item_id'] = self.generate_content_id(content)
                    self.logger.warning(f"内容缺少item_id，动态生成: {content['item_id']}")

                # 步骤1：依次尝试每个频道作为发送频道，直到成功（容错设计）
                send_success = False

                # 依次尝试每个频道作为发送频道，直到成功
                for potential_send_channel in target_channels:
                    try:
                        self.logger.info(f"尝试发送到频道 {potential_send_channel}: {content.get('title', '无标题')}")
                        
                        # 转换为统一消息格式
                        converter = get_converter(self.module_name)
                        telegram_message = converter.convert_to_telegram_message(content)
                        
                        # 使用统一发送器发送
                        messages = await self.sender.send_message(bot, potential_send_channel, telegram_message)
                        
                        if messages:
                            # 提取消息ID列表
                            message_ids = [msg.message_id for msg in messages]
                            self.save_message_mapping(source_url, content['item_id'], potential_send_channel, message_ids)
                            successful_channels[potential_send_channel] = message_ids  # 内存记录
                            self.logger.info(f"频道发送成功: {potential_send_channel}, 消息ID列表: {message_ids}")

                            send_success = True
                            # 更新统计信息（发送成功）
                            self.interval_manager.update_statistics(success=True)
                            break  # 成功后跳出循环
                    except Exception as send_error:
                        self.logger.warning(f"向 {potential_send_channel} 发送失败: {send_error}")
                        continue  # 尝试下一个频道

                # 如果所有频道发送都失败，跳过这个内容
                if not send_success:
                    self.logger.error(f"所有频道发送都失败，跳过内容: {content.get('title', '无标题')}")
                    # 更新统计信息（发送失败）
                    self.interval_manager.update_statistics(success=False)
                    continue

                # 步骤2：向剩余频道转发
                remaining_channels = [ch for ch in target_channels if ch not in successful_channels]
                if remaining_channels:
                    # 初始化转发专用间隔管理器
                    forward_interval_manager = UnifiedIntervalManager("forward")

                    for channel_index, channel in enumerate(remaining_channels):
                        success = False

                        # 转发前等待（使用转发专用间隔管理器）
                        await forward_interval_manager.wait_before_send(
                            content_index=channel_index,
                            total_content=len(remaining_channels),
                            recent_error_rate=forward_interval_manager.get_recent_error_rate()
                        )

                        # 从所有成功频道中尝试转发（统一处理，不区分发送频道）
                        for source_channel, source_msg_ids in successful_channels.items():
                            if source_channel != channel:  # 不从自己转发给自己
                                try:
                                    self.logger.info(f"尝试转发: {source_channel} -> {channel}")
                                    forwarded_messages = await bot.copy_messages(
                                        chat_id=channel,
                                        from_chat_id=source_channel,
                                        message_ids=source_msg_ids
                                    )
                                    # 处理返回的消息（可能是单个消息、消息列表或消息元组）
                                    if isinstance(forwarded_messages, (list, tuple)):
                                        forwarded_ids = [msg.message_id for msg in forwarded_messages]
                                    else:
                                        forwarded_ids = [forwarded_messages.message_id]
                                    self.save_message_mapping(source_url, content['item_id'], channel, forwarded_ids)
                                    successful_channels[channel] = forwarded_ids  # 内存记录
                                    self.logger.info(f"转发成功: {source_channel} -> {channel}, 消息ID列表: {forwarded_ids}")
                                    # 更新转发统计信息（转发成功）
                                    forward_interval_manager.update_statistics(success=True)
                                    success = True
                                    break  # 转发成功，跳出循环
                                except Exception as forward_error:
                                    self.logger.debug(f"从 {source_channel} 转发到 {channel} 失败: {forward_error}")
                                    # 检查是否是Flood Control错误（使用转发专用间隔管理器）
                                    if "flood control" in str(forward_error).lower():
                                        await forward_interval_manager.wait_after_error("flood_control")
                                    elif "rate limit" in str(forward_error).lower():
                                        await forward_interval_manager.wait_after_error("rate_limit")
                                    else:
                                        await forward_interval_manager.wait_after_error("other")
                                    continue  # 转发失败，尝试下一个源频道

                        # 所有转发都失败，最后降级为直接发送
                        if not success:
                            self.logger.warning(f"所有转发都失败，降级发送: {channel}")
                            try:
                                # 转换为统一消息格式
                                converter = get_converter(self.module_name)
                                telegram_message = converter.convert_to_telegram_message(content)
                                
                                # 使用统一发送器发送
                                fallback_messages = await self.sender.send_message(bot, channel, telegram_message)
                                
                                if fallback_messages:
                                    fallback_ids = [msg.message_id for msg in fallback_messages]
                                    self.save_message_mapping(source_url, content['item_id'], channel, fallback_ids)
                                    successful_channels[channel] = fallback_ids  # 内存记录
                                    self.logger.info(f"降级发送成功: {channel}")
                                    # 更新转发统计信息（降级发送成功）
                                    forward_interval_manager.update_statistics(success=True)
                            except Exception as send_error:
                                self.logger.error(f"降级发送也失败: {channel}, 错误: {send_error}", exc_info=True)
                                # 更新转发统计信息（降级发送失败）
                                forward_interval_manager.update_statistics(success=False)
                                continue

                    # 输出转发统计摘要（如果有转发操作）
                    if remaining_channels:
                        self.logger.info(f"📊 转发统计: {forward_interval_manager.get_statistics_summary()}")

                # 步骤3：标记内容已发送
                self.mark_item_as_sent(source_url, content)
                sent_count += 1

            except Exception as e:
                self.logger.error(f"发送内容失败: {content.get('title', '无标题')}, 错误: {e}", exc_info=True)
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

        self.logger.info(f"批量发送完成: 成功 {sent_count}/{len(content_items)} 个内容到 {len(target_channels)} 个频道")
        self.logger.info(f"📊 {self.interval_manager.get_statistics_summary()}")
        return sent_count

    def _sort_content_by_time(self, content_items: List[Dict]) -> List[Dict]:
        """
        按时间排序内容（从旧到新）

        Args:
            content_items: 内容列表

        Returns:
            List[Dict]: 排序后的内容列表
        """
        try:
            return sorted(content_items, key=lambda x: x.get('time', ''))
        except Exception as e:
            self.logger.warning(f"内容排序失败，使用原顺序: {e}")
            return content_items

    # ==================== 统计和维护接口 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取管理器统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            subscriptions = self.get_subscriptions()
            total_sources = len(subscriptions)
            total_channels = set()
            total_subscriptions = 0

            for channels in subscriptions.values():
                total_subscriptions += len(channels)
                total_channels.update(channels)

            return {
                "module_name": self.module_name,
                "total_sources": total_sources,
                "total_channels": len(total_channels),
                "total_subscriptions": total_subscriptions,
            }

        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}", exc_info=True)
            return {}


# 便捷函数：创建统一管理器的工厂方法
def create_unified_manager(module_name: str, manager_class, **kwargs) -> UnifiedContentManager:
    """
    创建统一管理器实例的工厂方法

    Args:
        module_name: 模块名称
        manager_class: 具体的管理器类
        **kwargs: 传递给管理器构造函数的参数

    Returns:
        UnifiedContentManager: 统一管理器实例
    """
    return manager_class(module_name=module_name, **kwargs)


if __name__ == "__main__":
    # 模块测试代码
    def test_unified_manager():
        """测试统一管理器功能"""
        print("🧪 统一管理器模块测试")

        # 这里只能测试抽象接口，具体实现需要在子类中测试
        print("✅ 统一管理器基类定义完成")
        print("📝 子类需要实现所有抽象方法")
        print("🎯 提供了完整的业务逻辑复用")

        print("🎉 统一管理器模块测试完成")

    # 运行测试
    test_unified_manager() 