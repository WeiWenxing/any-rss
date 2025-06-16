"""
Sitemap订阅服务模块

提供Sitemap订阅和推送功能，支持XML和TXT格式的Sitemap。
自动监控URL更新并推送到Telegram频道。

主要组件：
1. SitemapManager - Sitemap订阅管理器
2. SitemapParser - Sitemap解析器
3. SitemapSender - Sitemap消息发送器
4. register_sitemap_commands - 命令注册函数

作者: Assistant
创建时间: 2024年
"""

from .manager import SitemapManager, create_sitemap_manager
from .sitemap_parser import SitemapParser, create_sitemap_parser
from .sender import SitemapSender, create_sitemap_sender
from .commands import register_sitemap_commands

# 自动注册帮助信息提供者
from .help_provider import register_help_provider
register_help_provider()

__all__ = [
    # 核心管理器
    'SitemapManager',
    'create_sitemap_manager',

    # Sitemap解析器
    'SitemapParser',
    'create_sitemap_parser',

    # 消息发送器
    'SitemapSender',
    'create_sitemap_sender',

    # 命令注册
    'register_sitemap_commands'
] 