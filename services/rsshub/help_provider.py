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
            "• /rsshub_add <RSS链接> <频道ID> - 添加RSS订阅\n"
            "• /rsshub_del <RSS链接> <频道ID> - 删除RSS订阅\n"
            "• /rsshub_list [频道ID] - 查看订阅列表"
        )

    def get_debug_commands(self) -> str:
        """获取调试命令帮助信息"""
        return (
            "• /rsshub_debug_show <XML数据> - 通过文本调试RSS内容\n"
            "• /rss_debug_show_file - 上传包含XML的txt文件进行调试"
        )

    def get_examples(self) -> str:
        """获取使用示例"""
        return (
            "• /rsshub_add https://rsshub.app/github/issue/DIYgod/RSSHub @channel\n"
            "• /rsshub_list"
        )

    def get_description(self) -> str:
        """获取模块功能描述"""
        return "   • 支持RSS/Atom格式，自动推送新内容"

    def get_order_priority(self) -> int:
        """获取显示顺序优先级"""
        return 30  # RSSHub排在第三位


def register_help_provider():
    """注册RSSHub帮助信息提供者"""
    provider = RSSHubHelpProvider()
    get_help_manager().register_provider("rsshub", provider)