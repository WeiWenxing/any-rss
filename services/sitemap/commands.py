"""
Sitemap命令处理器模块

该模块负责处理所有Sitemap相关的Telegram命令，完全复用rsshub模块的命令处理逻辑。
支持Sitemap订阅的添加、删除和查看功能，提供统一的用户反馈体验。

主要功能：
1. /sitemap_add - 添加Sitemap订阅（包含完整的反馈流程）
2. /sitemap_del - 删除Sitemap订阅
3. /sitemap_list - 查看订阅列表
4. Sitemap URL验证和格式化
5. 统一的错误处理和用户反馈

作者: Assistant
创建时间: 2024年
"""

import logging
import asyncio
from typing import Dict, List, Tuple, Optional
from urllib.parse import urlparse
from telegram import Update, Bot
from telegram.ext import ContextTypes, CommandHandler, Application

from .manager import SitemapManager, create_sitemap_manager
from .sitemap_parser import SitemapParser, create_sitemap_parser
from services.common.unified_commands import UnifiedCommandHandler


class SitemapCommandHandler(UnifiedCommandHandler):
    """
    Sitemap命令处理器

    继承统一命令处理器基类，完全复用rsshub模块的命令处理逻辑
    """

    def __init__(self, data_dir: str = "storage/sitemap"):
        """
        初始化Sitemap命令处理器

        Args:
            data_dir: 数据存储目录
        """
        # 创建Sitemap管理器
        sitemap_manager = create_sitemap_manager(data_dir)

        # 调用父类构造函数
        super().__init__(module_name="sitemap", manager=sitemap_manager)

        # 初始化Sitemap特定组件
        self.sitemap_parser = create_sitemap_parser()

        self.logger.info("Sitemap命令处理器初始化完成")

    # ==================== 实现UnifiedCommandHandler抽象接口 ====================

    # 注意：get_source_display_name 现在使用基类默认实现，直接返回URL

    # ==================== 重写UnifiedCommandHandler的可选方法 ====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于用户反馈）

        Returns:
            str: 模块显示名称
        """
        return "Sitemap"


# 全局实例
_sitemap_command_handler = None


def get_sitemap_command_handler(data_dir: str = "storage/sitemap") -> SitemapCommandHandler:
    """
    获取Sitemap命令处理器实例（单例模式）

    Args:
        data_dir: 数据存储目录

    Returns:
        SitemapCommandHandler: 命令处理器实例
    """
    global _sitemap_command_handler
    if _sitemap_command_handler is None:
        _sitemap_command_handler = SitemapCommandHandler(data_dir)
    return _sitemap_command_handler


# ==================== Telegram命令处理函数 ====================

async def sitemap_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sitemap_add 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_sitemap_command_handler()
    await handler.handle_add_command(update, context)


async def sitemap_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sitemap_del 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_sitemap_command_handler()
    await handler.handle_remove_command(update, context)


async def sitemap_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sitemap_list 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_sitemap_command_handler()
    await handler.handle_list_command(update, context)


def register_commands(application: Application) -> None:
    """
    注册Sitemap相关的命令处理器

    Args:
        application: Telegram应用实例
    """
    # 导入debug配置
    from core.config import debug_config

    # 注册基础命令
    application.add_handler(CommandHandler("sitemap_add", sitemap_add_command))
    application.add_handler(CommandHandler("sitemap_del", sitemap_del_command))
    application.add_handler(CommandHandler("sitemap_list", sitemap_list_command))

    # 根据debug模式决定是否注册调试命令
    if debug_config["enabled"]:
        # 注册调试命令
        from .debug_commands import register_sitemap_debug_commands
        register_sitemap_debug_commands(application)
        logging.info("✅ Sitemap调试命令已注册（DEBUG模式开启）")
    else:
        logging.info("ℹ️ Sitemap调试命令已跳过（DEBUG模式关闭）")

    logging.info("Sitemap命令处理器注册完成") 