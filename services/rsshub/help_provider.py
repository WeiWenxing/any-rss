"""
RSSHub模块帮助信息提供者

提供RSSHub模块的帮助信息，包括基础命令、调试命令和使用示例。

作者: Assistant
创建时间: 2024年
"""

from services.common.help_provider import ModuleHelpProvider
from services.common.help_manager import get_help_manager


class RSSHubHelpProvider(ModuleHelpProvider):
    """RSSHub模块帮助信息提供者"""

    def get_module_name(self) -> str:
        """获取模块显示名称"""
        return "RSSHub订阅"

    def get_basic_commands(self) -> str:
        """获取基础命令帮助信息"""
        return (
            "🔹 /rsshub_add <RSS链接> <频道ID>\n"
            "   添加RSSHub订阅到指定频道\n"
            "   • 支持RSS 2.0和Atom 1.0格式\n"
            "   • 首次添加时会展示所有现有内容\n"
            "   • 频道ID格式：@channel_name 或 -1001234567890\n\n"
            "🔹 /rsshub_del <RSS链接> <频道ID>\n"
            "   删除RSSHub订阅\n"
            "   • 从指定频道移除RSS订阅源\n\n"
            "🔹 /rsshub_list [频道ID]\n"
            "   查看RSSHub订阅列表\n"
            "   • 不指定频道ID时显示所有订阅\n"
            "   • 指定频道ID时显示该频道的订阅\n"
            "   • 提供可点击复制的删除命令"
        )

    def get_debug_commands(self) -> str:
        """获取调试命令帮助信息"""
        return (
            "🔹 /rsshub_debug_show <XML数据>\n"
            "   调试RSSHub内容格式化和发送\n"
            "   • 用于测试单个RSS item的消息格式\n"
            "   • 接受XML格式的RSS item数据\n"
            "   • 包含格式化预览和实际消息发送\n"
            "   • 测试媒体提取和转换功能"
        )

    def get_examples(self) -> str:
        """获取使用示例"""
        return (
            "• /rsshub_add https://rsshub.app/github/issue/DIYgod/RSSHub @tech_channel\n"
            "• /rsshub_add https://rsshub.app/bilibili/user/video/123456 @video_channel\n"
            "• /rsshub_del https://rsshub.app/github/issue/DIYgod/RSSHub @tech_channel\n"
            "• /rsshub_list\n"
            "• /rsshub_list @tech_channel"
        )

    def get_description(self) -> str:
        """获取模块功能描述"""
        return (
            "   • 支持RSS 2.0和Atom 1.0格式\n"
            "   • 自动推送新发布的RSS内容\n"
            "   • 智能媒体提取和展示\n"
            "   • 支持多频道订阅管理"
        )

    def get_order_priority(self) -> int:
        """获取显示顺序优先级"""
        return 30  # RSSHub排在第三位


def register_help_provider():
    """注册RSSHub帮助信息提供者"""
    provider = RSSHubHelpProvider()
    get_help_manager().register_provider("rsshub", provider)