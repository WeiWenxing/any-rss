"""
RSSHub命令处理器模块

该模块负责处理所有RSSHub相关的Telegram命令，完全复用douyin模块的命令处理逻辑。
支持RSS订阅的添加、删除和查看功能，提供统一的用户反馈体验。

主要功能：
1. /rsshub_add - 添加RSS订阅（包含完整的反馈流程）
2. /rsshub_del - 删除RSS订阅
3. /rsshub_list - 查看订阅列表
4. RSS URL验证和格式化
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

from .manager import RSSHubManager, create_rsshub_manager
from .rss_parser import RSSParser, create_rss_parser
from services.common.unified_commands import UnifiedCommandHandler


class RSSHubCommandHandler(UnifiedCommandHandler):
    """
    RSSHub命令处理器

    继承统一命令处理器基类，完全复用douyin模块的命令处理逻辑
    """

    def __init__(self, data_dir: str = "storage/rsshub"):
        """
        初始化RSSHub命令处理器

        Args:
            data_dir: 数据存储目录
        """
        # 创建RSSHub管理器
        rsshub_manager = create_rsshub_manager(data_dir)

        # 调用父类构造函数
        super().__init__(module_name="rsshub", manager=rsshub_manager)

        # 初始化RSS特定组件
        self.rss_parser = create_rss_parser()

        self.logger.info("RSSHub命令处理器初始化完成")

    # ==================== 实现UnifiedCommandHandler抽象接口 ====================

    def get_source_display_name(self, source_url: str) -> str:
        """
        获取RSS源的显示名称（不请求API，避免浪费调用次数）

        Args:
            source_url: RSS源URL

        Returns:
            str: 显示名称
        """
        # 直接返回URL，不请求API获取标题
        return source_url

    # ==================== 重写UnifiedCommandHandler的可选方法 ====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于用户反馈）

        Returns:
            str: 模块显示名称
        """
        return "RSS"


# 全局实例
_rsshub_command_handler = None


def get_rsshub_command_handler(data_dir: str = "storage/rsshub") -> RSSHubCommandHandler:
    """
    获取RSSHub命令处理器实例（单例模式）

    Args:
        data_dir: 数据存储目录

    Returns:
        RSSHubCommandHandler: 命令处理器实例
    """
    global _rsshub_command_handler
    if _rsshub_command_handler is None:
        _rsshub_command_handler = RSSHubCommandHandler(data_dir)
    return _rsshub_command_handler


# ==================== Telegram命令处理函数 ====================

async def rsshub_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_add 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_rsshub_command_handler()
    await handler.handle_add_command(update, context)


async def rsshub_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_del 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_rsshub_command_handler()
    await handler.handle_remove_command(update, context)


async def rsshub_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /rsshub_list 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_rsshub_command_handler()
    await handler.handle_list_command(update, context)


def register_rsshub_commands(application: Application) -> None:
    """
    注册RSSHub相关的命令处理器

    Args:
        application: Telegram应用实例
    """
    # 导入debug配置
    from core.config import debug_config

    # 注册基础命令
    application.add_handler(CommandHandler("rsshub_add", rsshub_add_command))
    application.add_handler(CommandHandler("rsshub_del", rsshub_del_command))
    application.add_handler(CommandHandler("rsshub_list", rsshub_list_command))

    # 根据debug模式决定是否注册调试命令
    if debug_config["enabled"]:
        # 注册调试命令
        from .debug_commands import register_rsshub_debug_commands
        register_rsshub_debug_commands(application)
        logging.info("✅ RSSHub调试命令已注册（DEBUG模式开启）")
    else:
        logging.info("ℹ️ RSSHub调试命令已跳过（DEBUG模式关闭）")

    logging.info("RSSHub命令处理器注册完成")