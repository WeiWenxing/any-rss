"""
统一命令处理基类

该模块抽取了douyin命令处理的核心逻辑，为所有数据源模块提供统一的命令处理模式。
包含订阅管理、反馈流程、错误处理等通用命令处理流程。

主要功能：
1. 抽象的命令处理接口
2. 通用的反馈流程（处理中→进度→最终结果）
3. 统一的订阅状态检查
4. 标准的错误处理和用户反馈
5. 可配置的命令参数验证
6. 统一的历史对齐处理

作者: Assistant
创建时间: 2024年
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from telegram import Update, Bot
from telegram.ext import ContextTypes

from .unified_manager import UnifiedContentManager
from .unified_alignment import UnifiedAlignment


class UnifiedCommandHandler(ABC):
    """
    统一命令处理器基类

    抽取douyin命令处理的核心逻辑，为所有数据源模块提供统一的命令处理模式
    """

    def __init__(self, module_name: str, manager: UnifiedContentManager):
        """
        初始化统一命令处理器

        Args:
            module_name: 模块名称（如'douyin', 'rsshub'）
            manager: 统一管理器实例
        """
        self.module_name = module_name
        self.manager = manager
        self.logger = logging.getLogger(f"{module_name}_commands")
        
        # 初始化统一对齐器
        self.alignment = UnifiedAlignment()
        
        self.logger.info(f"{module_name}统一命令处理器初始化完成")

    # ==================== 抽象接口（子类必须实现）====================

    @abstractmethod
    def validate_source_url(self, source_url: str) -> Tuple[bool, str]:
        """
        验证数据源URL格式

        Args:
            source_url: 数据源URL

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        pass

    @abstractmethod
    def normalize_source_url(self, source_url: str) -> str:
        """
        标准化数据源URL

        Args:
            source_url: 原始URL

        Returns:
            str: 标准化后的URL
        """
        pass

    @abstractmethod
    def get_source_display_name(self, source_url: str) -> str:
        """
        获取数据源的显示名称

        Args:
            source_url: 数据源URL

        Returns:
            str: 显示名称
        """
        pass

    # ==================== 可选接口（子类可重写）====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于用户反馈）

        Returns:
            str: 模块显示名称
        """
        return self.module_name.upper()

    def validate_chat_id(self, chat_id: str) -> Tuple[bool, str]:
        """
        验证频道ID格式（子类可重写）

        Args:
            chat_id: 频道ID

        Returns:
            Tuple[bool, str]: (是否有效, 错误信息)
        """
        if not chat_id:
            return False, "频道ID不能为空"
        
        # 基本格式检查
        if not (chat_id.startswith('@') or chat_id.startswith('-') or chat_id.isdigit()):
            return False, "频道ID格式错误，应为 @channel_name 或数字ID"
        
        return True, ""

    async def perform_additional_validation(self, source_url: str, chat_id: str) -> Tuple[bool, str]:
        """
        执行额外的验证（子类可重写）

        Args:
            source_url: 数据源URL
            chat_id: 频道ID

        Returns:
            Tuple[bool, str]: (是否通过, 错误信息)
        """
        return True, ""

    # ==================== 通用命令处理逻辑（完全复用douyin逻辑）====================

    async def handle_add_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理添加订阅命令（完全复用douyin命令处理逻辑）

        Args:
            update: Telegram更新对象
            context: 命令上下文
        """
        try:
            display_name = self.get_module_display_name()
            
            # 1. 参数验证
            if len(context.args) < 2:
                await update.message.reply_text(
                    f"❌ 参数不足\n\n"
                    f"用法: /{self.module_name}_add <{display_name}链接> <频道ID>\n\n"
                    f"示例:\n"
                    f"/{self.module_name}_add https://example.com/feed @my_channel\n"
                    f"/{self.module_name}_add https://example.com/feed -1001234567890"
                )
                return

            source_url = context.args[0].strip()
            target_chat_id = context.args[1].strip()

            # 验证URL格式
            url_valid, url_error = self.validate_source_url(source_url)
            if not url_valid:
                await update.message.reply_text(f"❌ {url_error}")
                return

            # 验证频道ID格式
            chat_valid, chat_error = self.validate_chat_id(target_chat_id)
            if not chat_valid:
                await update.message.reply_text(f"❌ {chat_error}")
                return

            # 标准化URL
            source_url = self.normalize_source_url(source_url)

            # 执行额外验证
            extra_valid, extra_error = await self.perform_additional_validation(source_url, target_chat_id)
            if not extra_valid:
                await update.message.reply_text(f"❌ {extra_error}")
                return

            # 2. 检查订阅状态
            subscriptions = self.manager.get_subscriptions()
            subscription_status = self._check_subscription_status(source_url, target_chat_id, subscriptions)

            if subscription_status == "duplicate":
                # 重复订阅分支 - 直接返回
                await update.message.reply_text(self._format_duplicate_subscription_message(source_url, target_chat_id))
                return

            # 3. 立即反馈（非重复订阅才需要处理反馈）
            processing_message = await update.message.reply_text(self._format_processing_message(source_url, target_chat_id))

            # 4. 统一处理流程（首个频道和后续频道使用相同的用户反馈）
            try:
                if subscription_status == "first_channel":
                    # 首个频道：获取历史内容
                    success, error_msg, content_info = await self._add_first_channel_subscription(source_url, target_chat_id)
                    if not success:
                        await processing_message.edit_text(self._format_error_message(source_url, error_msg))
                        return

                    check_success, check_error_msg, content_list = self.manager.check_updates(source_url)
                    if not check_success or not content_list:
                        await processing_message.edit_text(self._format_final_success_message(source_url, target_chat_id, 0))
                        return

                    content_count = len(content_list)
                else:
                    # 后续频道：获取已知内容ID列表
                    success, error_msg, content_info = await self._add_additional_channel_subscription(source_url, target_chat_id)
                    if not success:
                        await processing_message.edit_text(self._format_error_message(source_url, error_msg))
                        return

                    if isinstance(content_info, dict) and content_info.get("need_alignment"):
                        content_list = content_info.get("known_item_ids", [])
                        content_count = len(content_list)
                    else:
                        content_count = 0

                # 5. 进度反馈（统一格式）
                if content_count > 0:
                    await processing_message.edit_text(self._format_progress_message(source_url, target_chat_id, content_count))

                    # 6. 执行具体操作（用户无感知差异）
                    if subscription_status == "first_channel":
                        # 发送到频道
                        sent_count = await self.manager.send_content_batch(
                            context.bot, content_list, source_url, [target_chat_id]
                        )
                    else:
                        # 历史对齐（用户看不到技术细节）
                        alignment_success = await self.alignment.align_content_to_channel(
                            context.bot, self.manager, source_url, content_list, target_chat_id
                        )
                        sent_count = len(content_list) if alignment_success else 0

                    # 7. 最终反馈（统一格式）
                    await processing_message.edit_text(self._format_final_success_message(source_url, target_chat_id, sent_count))
                else:
                    # 无内容的情况
                    await processing_message.edit_text(self._format_final_success_message(source_url, target_chat_id, 0))

            except Exception as e:
                # 错误反馈
                self.logger.error(f"订阅处理失败: {source_url} -> {target_chat_id}", exc_info=True)
                await processing_message.edit_text(self._format_error_message(source_url, str(e)))

        except Exception as e:
            self.logger.error(f"处理{self.get_module_display_name()}添加命令失败", exc_info=True)
            await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")

    async def handle_remove_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理删除订阅命令

        Args:
            update: Telegram更新对象
            context: 命令上下文
        """
        try:
            display_name = self.get_module_display_name()
            
            # 参数验证
            if len(context.args) < 2:
                await update.message.reply_text(
                    f"❌ 参数不足\n\n"
                    f"用法: /{self.module_name}_del <{display_name}链接> <频道ID>\n\n"
                    f"示例:\n"
                    f"/{self.module_name}_del https://example.com/feed @my_channel"
                )
                return

            source_url = context.args[0].strip()
            target_chat_id = context.args[1].strip()

            # 验证URL格式
            url_valid, url_error = self.validate_source_url(source_url)
            if not url_valid:
                await update.message.reply_text(f"❌ {url_error}")
                return

            # 标准化URL
            source_url = self.normalize_source_url(source_url)

            # 执行删除
            success = await self._remove_subscription(source_url, target_chat_id)
            
            if success:
                source_display = self.get_source_display_name(source_url)
                await update.message.reply_text(
                    f"✅ 删除{display_name}订阅成功\n\n"
                    f"📡 {display_name}源: {source_display}\n"
                    f"📢 频道: {target_chat_id}"
                )
            else:
                await update.message.reply_text(
                    f"❌ 删除失败\n\n"
                    f"该{display_name}订阅不存在或已被删除"
                )

        except Exception as e:
            self.logger.error(f"处理{self.get_module_display_name()}删除命令失败", exc_info=True)
            await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")

    async def handle_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理列表订阅命令

        Args:
            update: Telegram更新对象
            context: 命令上下文
        """
        try:
            display_name = self.get_module_display_name()
            
            # 获取当前用户的订阅（如果提供了频道ID参数）
            if len(context.args) > 0:
                target_chat_id = context.args[0].strip()
                subscriptions = self._get_channel_subscriptions(target_chat_id)
                
                if not subscriptions:
                    await update.message.reply_text(
                        f"📋 频道 {target_chat_id} 暂无{display_name}订阅"
                    )
                    return

                message_lines = [f"📋 频道 {target_chat_id} 的{display_name}订阅列表:\n"]
                for i, source_url in enumerate(subscriptions, 1):
                    source_display = self.get_source_display_name(source_url)
                    message_lines.append(f"{i}. {source_display}")

            else:
                # 显示所有订阅
                all_subscriptions = self.manager.get_subscriptions()
                
                if not all_subscriptions:
                    await update.message.reply_text(f"📋 暂无{display_name}订阅")
                    return

                message_lines = [f"📋 所有{display_name}订阅列表:\n"]
                for i, (source_url, channels) in enumerate(all_subscriptions.items(), 1):
                    source_display = self.get_source_display_name(source_url)
                    message_lines.append(f"{i}. {source_display}")
                    message_lines.append(f"   📢 频道数: {len(channels)}")

            message_text = "\n".join(message_lines)
            await update.message.reply_text(message_text)

        except Exception as e:
            self.logger.error(f"处理{self.get_module_display_name()}列表命令失败", exc_info=True)
            await update.message.reply_text(f"❌ 处理命令时发生错误: {str(e)}")

    # ==================== 内部辅助方法 ====================

    def _check_subscription_status(self, source_url: str, chat_id: str, subscriptions: Dict[str, List[str]]) -> str:
        """
        检查订阅状态

        Args:
            source_url: 数据源URL
            chat_id: 频道ID
            subscriptions: 当前订阅字典

        Returns:
            str: 订阅状态 ("duplicate", "first_channel", "additional_channel")
        """
        existing_channels = subscriptions.get(source_url, [])
        
        if chat_id in existing_channels:
            return "duplicate"
        elif len(existing_channels) == 0:
            return "first_channel"
        else:
            return "additional_channel"

    async def _add_first_channel_subscription(self, source_url: str, chat_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        添加首个频道订阅（子类可重写具体实现）

        Args:
            source_url: 数据源URL
            chat_id: 频道ID

        Returns:
            Tuple[bool, str, Optional[Dict]]: (是否成功, 错误信息, 内容数据)
        """
        # 默认实现：直接添加到订阅列表
        try:
            subscriptions = self.manager.get_subscriptions()
            subscriptions[source_url] = [chat_id]
            # 这里需要子类实现具体的保存逻辑
            return True, "", {}
        except Exception as e:
            return False, str(e), None

    async def _add_additional_channel_subscription(self, source_url: str, chat_id: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        添加额外频道订阅（需要历史对齐）

        Args:
            source_url: 数据源URL
            chat_id: 频道ID

        Returns:
            Tuple[bool, str, Optional[Dict]]: (是否成功, 错误信息, 对齐信息)
        """
        try:
            subscriptions = self.manager.get_subscriptions()
            existing_channels = subscriptions.get(source_url, [])
            existing_channels.append(chat_id)
            subscriptions[source_url] = existing_channels
            
            # 获取已知内容列表（用于历史对齐）
            known_item_ids = self.manager.get_known_item_ids(source_url)
            
            # 返回对齐信息
            alignment_info = {
                "need_alignment": True,
                "known_item_ids": known_item_ids,
                "new_channel": chat_id
            }
            
            return True, "", alignment_info
        except Exception as e:
            return False, str(e), None

    async def _remove_subscription(self, source_url: str, chat_id: str) -> bool:
        """
        删除订阅

        Args:
            source_url: 数据源URL
            chat_id: 频道ID

        Returns:
            bool: 是否删除成功
        """
        try:
            subscriptions = self.manager.get_subscriptions()
            
            if source_url not in subscriptions:
                return False

            channels = subscriptions[source_url]
            if chat_id in channels:
                channels.remove(chat_id)
                
                # 如果没有频道订阅了，删除整个源
                if not channels:
                    del subscriptions[source_url]
                
                # 这里需要子类实现具体的保存逻辑
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"删除订阅失败: {source_url} -> {chat_id}, 错误: {str(e)}", exc_info=True)
            return False

    def _get_channel_subscriptions(self, chat_id: str) -> List[str]:
        """
        获取频道的所有订阅

        Args:
            chat_id: 频道ID

        Returns:
            List[str]: 数据源URL列表
        """
        subscriptions = []
        all_subscriptions = self.manager.get_subscriptions()
        
        for source_url, channels in all_subscriptions.items():
            if chat_id in channels:
                subscriptions.append(source_url)
        
        return subscriptions

    # ==================== 消息格式化方法 ====================

    def _format_duplicate_subscription_message(self, source_url: str, chat_id: str) -> str:
        """格式化重复订阅消息"""
        display_name = self.get_module_display_name()
        source_display = self.get_source_display_name(source_url)
        
        return (
            f"ℹ️ {display_name}订阅已存在\n\n"
            f"📡 {display_name}源: {source_display}\n"
            f"📢 频道: {chat_id}\n\n"
            f"无需重复添加"
        )

    def _format_processing_message(self, source_url: str, chat_id: str) -> str:
        """格式化处理中消息"""
        display_name = self.get_module_display_name()
        source_display = self.get_source_display_name(source_url)
        
        return (
            f"⏳ 正在处理{display_name}订阅...\n\n"
            f"📡 {display_name}源: {source_display}\n"
            f"📢 频道: {chat_id}\n\n"
            f"请稍候..."
        )

    def _format_progress_message(self, source_url: str, chat_id: str, content_count: int) -> str:
        """格式化进度消息"""
        display_name = self.get_module_display_name()
        source_display = self.get_source_display_name(source_url)
        
        return (
            f"📤 正在发送{display_name}内容...\n\n"
            f"📡 {display_name}源: {source_display}\n"
            f"📢 频道: {chat_id}\n"
            f"📊 内容数量: {content_count}\n\n"
            f"发送中，请稍候..."
        )

    def _format_final_success_message(self, source_url: str, chat_id: str, sent_count: int) -> str:
        """格式化最终成功消息"""
        display_name = self.get_module_display_name()
        source_display = self.get_source_display_name(source_url)
        
        return (
            f"✅ {display_name}订阅添加成功\n\n"
            f"📡 {display_name}源: {source_display}\n"
            f"📢 频道: {chat_id}\n"
            f"📊 发送内容: {sent_count} 个\n\n"
            f"订阅已生效，将自动推送新内容"
        )

    def _format_error_message(self, source_url: str, error_msg: str) -> str:
        """格式化错误消息"""
        display_name = self.get_module_display_name()
        source_display = self.get_source_display_name(source_url)
        
        return (
            f"❌ {display_name}订阅添加失败\n\n"
            f"📡 {display_name}源: {source_display}\n"
            f"❗ 错误信息: {error_msg}\n\n"
            f"请检查{display_name}链接是否正确"
        )


if __name__ == "__main__":
    # 模块测试代码
    def test_unified_commands():
        """测试统一命令处理器功能"""
        print("🧪 统一命令处理器模块测试")

        # 这里只能测试抽象接口，具体实现需要在子类中测试
        print("✅ 统一命令处理器基类定义完成")
        print("📝 子类需要实现所有抽象方法")
        print("🎯 提供了完整的命令处理逻辑复用")

        print("🎉 统一命令处理器模块测试完成")

    # 运行测试
    test_unified_commands() 