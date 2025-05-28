"""
抖音订阅服务模块

提供抖音用户内容订阅和推送功能
"""

from .manager import DouyinManager
from .commands import register_douyin_commands

# 自动注册帮助信息提供者
from .help_provider import register_help_provider
register_help_provider()

__all__ = ['DouyinManager', 'register_douyin_commands']