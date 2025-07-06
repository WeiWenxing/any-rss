"""
Sample命令处理器模块

该模块负责处理所有Sample相关的Telegram命令，继承统一命令处理器基类。
支持样本账号订阅的添加、删除和查看功能，提供统一的用户反馈体验。

主要功能：
1. /sample_add - 添加样本账号订阅（包含完整的反馈流程）
2. /sample_del - 删除样本账号订阅
3. /sample_list - 查看订阅列表
4. 样本URL验证和格式化
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

from services.common.unified_commands import UnifiedCommandHandler
from .manager import create_sample_manager


class SampleCommandHandler(UnifiedCommandHandler):
    """
    Sample命令处理器

    继承统一命令处理器基类，提供样本账号订阅管理功能
    """

    def __init__(self, data_dir: str = "storage/sample"):
        """
        初始化Sample命令处理器

        Args:
            data_dir: 数据存储目录
        """
        # 创建Sample管理器
        sample_manager = create_sample_manager(data_dir)

        # 调用父类构造函数
        super().__init__(module_name="sample", manager=sample_manager)

        self.logger.info("Sample命令处理器初始化完成")

    # ==================== 重写UnifiedCommandHandler的方法 ====================

    def get_module_display_name(self) -> str:
        """
        获取模块显示名称（用于用户反馈）

        Returns:
            str: 模块显示名称
        """
        return "样本订阅 (Sample)"

    def get_source_display_name(self, source_url: str) -> str:
        """
        获取数据源的显示名称

        Args:
            source_url: 样本链接

        Returns:
            str: 显示名称
        """
        # 暂时直接返回URL，后续可以实现解析用户名
        return source_url






# 全局实例
_sample_command_handler = None


def get_sample_command_handler(data_dir: str = "storage/sample") -> SampleCommandHandler:
    """
    获取Sample命令处理器实例（单例模式）

    Args:
        data_dir: 数据存储目录

    Returns:
        SampleCommandHandler: 命令处理器实例
    """
    global _sample_command_handler
    if _sample_command_handler is None:
        _sample_command_handler = SampleCommandHandler(data_dir)
    return _sample_command_handler


# ==================== Telegram命令处理函数 ====================

async def sample_add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sample_add 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_sample_command_handler()
    await handler.handle_add_command(update, context)


async def sample_del_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sample_del 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_sample_command_handler()
    await handler.handle_remove_command(update, context)


async def sample_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    处理 /sample_list 命令

    Args:
        update: Telegram更新对象
        context: 命令上下文
    """
    handler = get_sample_command_handler()
    await handler.handle_list_command(update, context)


def register_sample_commands(application: Application) -> None:
    """
    注册Sample相关的命令处理器

    Args:
        application: Telegram应用实例
    """
    # 导入debug配置
    from core.config import debug_config

    # 注册基础命令
    application.add_handler(CommandHandler("sample_add", sample_add_command))
    application.add_handler(CommandHandler("sample_del", sample_del_command))
    application.add_handler(CommandHandler("sample_list", sample_list_command))

    # 根据debug模式决定是否注册调试命令
    if debug_config["enabled"]:
        # 注册调试命令
        from .debug_commands import register_sample_debug_commands
        register_sample_debug_commands(application)
        logging.info("✅ Sample调试命令已注册（DEBUG模式开启）")
    else:
        logging.info("ℹ️ Sample调试命令已跳过（DEBUG模式关闭）")

    logging.info("Sample命令处理器注册完成") 