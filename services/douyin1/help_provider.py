"""
Douyin1模块帮助信息提供者

提供Douyin1模块的帮助信息，包括基础命令、调试命令和使用示例。
支持抖音账号订阅的完整帮助文档。

作者: Assistant
创建时间: 2024年
"""

from services.common.help_provider import ModuleHelpProvider
from services.common.help_manager import get_help_manager


class Douyin1HelpProvider(ModuleHelpProvider):
    """Douyin1模块帮助信息提供者"""

    def get_module_name(self) -> str:
        """获取模块显示名称"""
        return "抖音订阅 (Douyin1)"

    def get_basic_commands(self) -> str:
        """获取基础命令帮助信息"""
        return (
            "• /douyin1_add <抖音链接> <频道ID> - 添加抖音账号订阅\n"
            "• /douyin1_del <抖音链接> <频道ID> - 删除抖音账号订阅\n"
            "• /douyin1_list [频道ID] - 查看订阅列表"
        )

    def get_debug_commands(self) -> str:
        """获取调试命令帮助信息"""
        return (
            "• /douyin1_debug_check <抖音链接> - 检查抖音账号状态\n"
            "• /douyin1_debug_fetch <抖音链接> - 手动获取最新内容\n"
            "• /douyin1_debug_stats - 查看模块统计信息"
        )

    def get_examples(self) -> str:
        """获取使用示例"""
        return (
            "• /douyin1_add https://www.douyin.com/user/MS4wLjABAAAA... @mychannel\n"
            "• /douyin1_add https://v.douyin.com/iM5g7LsM/ -1001234567890\n"
            "• /douyin1_list @mychannel\n"
            "• /douyin1_del https://www.douyin.com/user/MS4wLjABAAAA... @mychannel"
        )

    def get_description(self) -> str:
        """获取模块功能描述"""
        return "   • 支持抖音账号订阅，自动推送最新视频和动态"

    def get_order_priority(self) -> int:
        """获取显示顺序优先级"""
        return 25  # 在douyin(20)之后，rss(30)之前


def register_help_provider():
    """注册Douyin1帮助信息提供者"""
    provider = Douyin1HelpProvider()
    get_help_manager().register_provider("douyin1", provider) 