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
        # 暂时直接返回URL，后续可以实现解析用户名
        return source_url


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