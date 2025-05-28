"""
RSSHub订阅服务模块

该模块提供RSS/Atom订阅和推送功能，完全复用douyin模块的架构设计。
支持RSS源的订阅管理、内容解析、消息转换和定时推送。

主要组件：
1. RSSHubManager - RSS订阅管理器
2. RSSParser - RSS/Atom解析器
3. RSSMessageConverter - RSS消息转换器
4. RSSHubScheduler - RSS定时调度器
5. register_rsshub_commands - 命令注册函数

作者: Assistant
创建时间: 2024年
"""

from .manager import RSSHubManager, create_rsshub_manager
from .rss_parser import RSSParser, create_rss_parser
from .rss_converter import RSSMessageConverter, create_rss_converter
from .rss_entry import RSSEntry, RSSEnclosure, create_rss_entry
from .scheduler import RSSHubScheduler, create_rsshub_scheduler
from .commands import register_rsshub_commands

# 自动注册RSS消息转换器到全局注册表
from services.common.message_converter import register_converter
_rss_converter = create_rss_converter()
register_converter(_rss_converter)

# 自动注册帮助信息提供者
from .help_provider import register_help_provider
register_help_provider()

__all__ = [
    # 核心管理器
    'RSSHubManager',
    'create_rsshub_manager',

    # RSS解析器
    'RSSParser',
    'create_rss_parser',

    # 消息转换器
    'RSSMessageConverter',
    'create_rss_converter',

    # RSS实体
    'RSSEntry',
    'RSSEnclosure',
    'create_rss_entry',

    # 调度器
    'RSSHubScheduler',
    'create_rsshub_scheduler',

    # 命令注册
    'register_rsshub_commands'
]