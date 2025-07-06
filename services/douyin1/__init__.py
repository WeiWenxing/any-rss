"""
模块 - 内容订阅服务

该模块提供内容的订阅、管理和推送功能，支持用户订阅账号并自动推送最新内容到指定频道。
本模块是作为新模块开发的模板，采用统一的架构设计。

主要功能：
1. 账号订阅管理
2. 自动内容检测和推送
3. 历史内容对齐
4. 多频道订阅支持
5. 调试和监控功能

模块结构：
- commands.py: 命令处理器（继承UnifiedCommandHandler）
- help_provider.py: 帮助信息提供者
- debug_commands.py: 调试命令
- manager.py: 内容管理器（待实现）
- fetcher.py: 内容获取器（待实现）
- formatter.py: 内容格式化器（待实现）
- sender.py: 内容发送器（待实现）

作者: Assistant
创建时间: 2024年
版本: 1.0.0
"""

import logging
from typing import Dict, List, Optional

# ==================== 模块配置（新模块只需修改这里）====================
# 模块名称（用于命令前缀，如 douyin1_add, douyin1_del 等）
MODULE_NAME = "douyin1"
# 模块显示名称（用于用户界面显示）
MODULE_DISPLAY_NAME = "抖音订阅 (Douyin1)"
# 模块描述
MODULE_DESCRIPTION = "抖音内容订阅服务"
# 数据存储目录前缀
DATA_DIR_PREFIX = "storage/douyin1"

# ==================== 模块信息 ====================
__version__ = "1.0.0"
__author__ = "Assistant"
__description__ = MODULE_DESCRIPTION

# 初始化日志
logger = logging.getLogger(__name__)
logger.info(f"{MODULE_DISPLAY_NAME}模块初始化 - 版本: {__version__}")

# 模块状态
_module_initialized = False
_command_handlers_registered = False


def get_module_info() -> Dict[str, str]:
    """
    获取模块信息

    Returns:
        Dict[str, str]: 模块信息字典
    """
    return {
        "name": MODULE_NAME,
        "display_name": MODULE_DISPLAY_NAME,
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "status": "initialized" if _module_initialized else "not_initialized"
    }


def get_command_names() -> Dict[str, str]:
    """
    获取动态生成的命令名称

    Returns:
        Dict[str, str]: 命令名称字典
    """
    return {
        "add": f"{MODULE_NAME}_add",
        "del": f"{MODULE_NAME}_del",
        "list": f"{MODULE_NAME}_list",
        "debug_show": f"{MODULE_NAME}_debug_show"
    }


# 自动注册帮助信息提供者
from .help_provider import register_help_provider
register_help_provider()


def initialize_module(data_dir: str = None) -> bool:
    """
    初始化模块

    Args:
        data_dir: 数据存储目录（可选，默认使用模块配置）

    Returns:
        bool: 是否初始化成功
    """
    global _module_initialized

    if data_dir is None:
        data_dir = DATA_DIR_PREFIX

    try:
        logger.info(f"开始初始化{MODULE_DISPLAY_NAME}模块 - 数据目录: {data_dir}")

        _module_initialized = True
        logger.info(f"✅ {MODULE_DISPLAY_NAME}模块初始化完成")
        return True

    except Exception as e:
        logger.error(f"❌ {MODULE_DISPLAY_NAME}模块初始化失败: {e}", exc_info=True)
        return False


def is_module_initialized() -> bool:
    """
    检查模块是否已初始化

    Returns:
        bool: 是否已初始化
    """
    return _module_initialized


# 导入主要组件
from .manager import ContentManager, create_content_manager
from .commands import register_commands

# 导出主要组件
__all__ = [
    # 模块配置
    "MODULE_NAME",
    "MODULE_DISPLAY_NAME",
    "MODULE_DESCRIPTION",
    "DATA_DIR_PREFIX",

    # 模块信息
    "get_module_info",
    "get_command_names",
    "initialize_module",
    "is_module_initialized",
    "__version__",
    "__author__",
    "__description__",

    # 核心组件
    "ContentManager",
    "create_content_manager",
    "register_commands"
] 