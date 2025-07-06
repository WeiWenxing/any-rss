"""
Douyin1模块 - 抖音内容订阅服务 (第二版本)

该模块提供抖音内容的订阅、管理和推送功能，支持用户订阅抖音账号并自动推送最新内容到指定频道。
本模块是douyin模块的改进版本，采用统一的架构设计。

主要功能：
1. 抖音账号订阅管理
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

# 模块信息
__version__ = "1.0.0"
__author__ = "Assistant"
__description__ = "抖音内容订阅服务 (第二版本)"

# 初始化日志
logger = logging.getLogger(__name__)
logger.info(f"Douyin1模块初始化 - 版本: {__version__}")

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
        "name": "douyin1",
        "version": __version__,
        "author": __author__,
        "description": __description__,
        "status": "initialized" if _module_initialized else "not_initialized"
    }


# 自动注册帮助信息提供者
from .help_provider import register_help_provider
register_help_provider()


def initialize_module(data_dir: str = "storage/douyin1") -> bool:
    """
    初始化模块
    
    Args:
        data_dir: 数据存储目录
        
    Returns:
        bool: 是否初始化成功
    """
    global _module_initialized
    
    try:
        logger.info(f"开始初始化Douyin1模块 - 数据目录: {data_dir}")
        
        _module_initialized = True
        logger.info("✅ Douyin1模块初始化完成")
        return True
        
    except Exception as e:
        logger.error(f"❌ Douyin1模块初始化失败: {e}", exc_info=True)
        return False


def is_module_initialized() -> bool:
    """
    检查模块是否已初始化
    
    Returns:
        bool: 是否已初始化
    """
    return _module_initialized


# 导出主要组件（当前只有命令处理器可用）
__all__ = [
    "get_module_info",
    "initialize_module", 
    "is_module_initialized",
    "__version__",
    "__author__",
    "__description__"
] 