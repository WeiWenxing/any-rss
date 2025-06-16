"""
Sitemap模块帮助信息提供者

提供Sitemap模块的帮助信息，包括基础命令、调试命令和使用示例。

作者: Assistant
创建时间: 2024年
"""

from services.common.help_provider import ModuleHelpProvider
from services.common.help_manager import get_help_manager


class SitemapHelpProvider(ModuleHelpProvider):
    """Sitemap模块帮助信息提供者"""

    def get_module_name(self) -> str:
        """获取模块显示名称"""
        return "Sitemap订阅"

    def get_basic_commands(self) -> str:
        """获取基础命令帮助信息"""
        return (
            "• /sitemap-add <Sitemap链接> <频道ID> - 添加Sitemap订阅\n"
            "• /sitemap-del <Sitemap链接> <频道ID> - 删除Sitemap订阅\n"
            "• /sitemap-list [频道ID] - 查看订阅列表"
        )

    def get_debug_commands(self) -> str:
        """获取调试命令帮助信息"""
        return (
            "• /sitemap-debug-show <XML数据> - 通过文本调试Sitemap内容"
        )

    def get_examples(self) -> str:
        """获取使用示例"""
        return (
            "• /sitemap-add https://example.com/sitemap.xml @channel\n"
            "• /sitemap-list"
        )

    def get_description(self) -> str:
        """获取模块功能描述"""
        return "   • 支持XML/TXT/GZIP格式，自动监控URL更新"

    def get_order_priority(self) -> int:
        """获取显示顺序优先级"""
        return 40  # Sitemap排在第四位


def register_help_provider():
    """注册Sitemap帮助信息提供者"""
    provider = SitemapHelpProvider()
    get_help_manager().register_provider("sitemap", provider) 