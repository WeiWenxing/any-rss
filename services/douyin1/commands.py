"""
命令处理器模块

该模块负责处理所有相关的Telegram命令，继承统一命令处理器基类。
支持账号订阅的添加、删除和查看功能，提供统一的用户反馈体验。

主要功能：
1. 动态命令生成（基于模块名自动生成命令前缀）
2. URL验证和格式化
3. 统一的错误处理和用户反馈

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

from services.common.unified_commands import UnifiedCommandHandler
from .manager import create_content_manager
from . import MODULE_NAME, MODULE_DISPLAY_NAME, DATA_DIR_PREFIX, get_command_names


class ModuleCommandHandler(UnifiedCommandHandler):
    """
    模块命令处理器

    继承统一命令处理器基类，提供账号订阅管理功能
    """

    def __init__(self, data_dir: str = None):
        """
        初始化模块命令处理器

        Args:
            data_dir: 数据存储目录（可选，默认使用模块配置）
        """
        if data_dir is None:
            data_dir = DATA_DIR_PREFIX

        # 创建内容管理器
        content_manager = create_content_manager(data_dir)

        # 调用父类构造函数
        super().__init__(module_name=MODULE_NAME, manager=content_manager)

        self.logger.info(f"{MODULE_DISPLAY_NAME}命令处理器初始化完成")

    # ==================== 重写UnifiedCommandHandler的方法 ====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于用户反馈）

        Returns:
            str: 模块显示名称
        """
        return MODULE_DISPLAY_NAME

    def get_source_display_name(self, source_url: str) -> str:
        """
        获取数据源的显示名称

        Args:
            source_url: 链接

        Returns:
            str: 显示名称
        """
        try:
            # 尝试从latest.json获取作者信息
            from pathlib import Path
            import json

            # 使用 UnifiedContentManager 的正确路径结构
            url_hash = self.manager._safe_filename(source_url)
            url_dir = self.manager.data_storage_dir / url_hash
            latest_file = url_dir / "latest.json"

            if latest_file.exists():
                latest_data = json.loads(latest_file.read_text(encoding='utf-8'))

                # 根据实际JSON结构获取作者信息
                # 作者信息在 author 对象中
                if "author" in latest_data and isinstance(latest_data["author"], dict):
                    author_info = latest_data["author"]
                    # 优先使用 nickname
                    if author_info.get("nickname"):
                        return author_info["nickname"]
                    # 其次使用 uid 作为备选
                    elif author_info.get("uid"):
                        return f"用户_{author_info['uid']}"

                # 兼容旧格式：直接在根级别的 nickname 或 author
                if latest_data.get("nickname"):
                    return latest_data["nickname"]
                elif latest_data.get("author"):
                    return latest_data["author"]

        except Exception as e:
            self.logger.warning(f"获取作者信息失败: {e}")

        # 默认返回"抖音链接"
        return "抖音链接"

    async def handle_list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        处理列表订阅命令（优化版本，参考douyin模块样式）

        Args:
            update: Telegram更新对象
            context: 命令上下文
        """
        try:
            user = update.message.from_user
            chat_id = update.message.chat_id
            self.logger.info(f"收到{self.module_name.upper()}_LIST命令 - 用户: {user.username}(ID:{user.id}) 聊天ID: {chat_id}")

            # 获取所有订阅
            subscriptions = self.manager.get_subscriptions()

            if not subscriptions:
                self.logger.info(f"{self.module_name}订阅列表为空")
                await update.message.reply_text(
                    f"*{self.get_module_display_name()}订阅列表*\n\n"
                    f"当前没有{self.get_module_display_name()}订阅\n\n"
                    f"使用 `/{self.module_name}_add <抖音链接> <频道ID>` 添加订阅",
                    parse_mode='Markdown'
                )
                return

            # 构建订阅列表内容
            message_lines = [f"*{self.get_module_display_name()}订阅列表*\n"]

            for source_url, target_channels in subscriptions.items():
                # 处理频道列表
                if isinstance(target_channels, list):
                    channels_display = ' | '.join([f'`{channel}`' for channel in target_channels])
                else:
                    # 兼容旧格式
                    channels_display = f'`{target_channels}`'

                # 获取作者信息用于锚文本
                author_name = self.get_source_display_name(source_url)

                # 添加订阅项：使用锚文本格式
                message_lines.append(f"[{author_name}]({source_url}) → {channels_display}")

            # 添加基础命令
            try:
                from services.common.help_manager import get_help_manager
                help_manager = get_help_manager()

                if self.module_name in help_manager.providers:
                    provider = help_manager.providers[self.module_name]
                    basic_commands = provider.get_basic_commands()

                    message_lines.append("\n*基础命令：*")
                    # 格式化命令，将下划线命令用代码块包围
                    import re
                    formatted_commands = re.sub(rf'/({self.module_name}_\w+)', r'`/\1`', basic_commands)
                    message_lines.append(formatted_commands)
                else:
                    self.logger.warning(f"未找到{self.module_name}模块的帮助信息提供者")
            except Exception as e:
                self.logger.warning(f"获取帮助信息失败: {str(e)}")

            # 发送消息
            message_text = '\n'.join(message_lines)
            self.logger.info(f"发送{self.module_name}订阅列表，共{len(subscriptions)}个订阅")
            await update.message.reply_text(message_text, parse_mode='Markdown')

        except Exception as e:
            self.logger.error(f"处理{self.module_name}_list命令失败: {str(e)}", exc_info=True)
            await update.message.reply_text(f"❌ 获取订阅列表失败: {str(e)}")


# 全局实例
_command_handler = None


def get_command_handler(data_dir: str = None) -> ModuleCommandHandler:
    """
    获取命令处理器实例（单例模式）

    Args:
        data_dir: 数据存储目录（可选，默认使用模块配置）

    Returns:
        ModuleCommandHandler: 命令处理器实例
    """
    global _command_handler
    if _command_handler is None:
        _command_handler = ModuleCommandHandler(data_dir)
    return _command_handler


# ==================== 通用命令处理函数 ====================

async def handle_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理添加订阅命令（动态生成）

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_command_handler()
    await handler.handle_add_command(update, context)


async def handle_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理删除订阅命令（动态生成）

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_command_handler()
    await handler.handle_remove_command(update, context)


async def handle_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理列表订阅命令（动态生成）

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_command_handler()
    await handler.handle_list_command(update, context)


def register_commands(application: Application) -> None:
    """
    注册模块相关的命令处理器（动态生成命令名称）

    Args:
        application: Telegram应用实例
    """
    # 获取动态生成的命令名称
    command_names = get_command_names()

    # 导入debug配置
    from core.config import debug_config

    # 注册基础命令（使用动态生成的命令名称）
    application.add_handler(CommandHandler(command_names["add"], handle_add_command))
    application.add_handler(CommandHandler(command_names["del"], handle_del_command))
    application.add_handler(CommandHandler(command_names["list"], handle_list_command))

    # 根据debug模式决定是否注册调试命令
    if debug_config["enabled"]:
        # 注册调试命令
        from .debug_commands import register_debug_commands
        register_debug_commands(application)
        logging.info(f"✅ {MODULE_DISPLAY_NAME}调试命令已注册（DEBUG模式开启）")
    else:
        logging.info(f"ℹ️ {MODULE_DISPLAY_NAME}调试命令已跳过（DEBUG模式关闭）")

    logging.info(f"{MODULE_DISPLAY_NAME}命令处理器注册完成")
    logging.info(f"📋 已注册命令: {', '.join([f'/{name}' for name in command_names.values()])}")