"""
抖音模块帮助信息提供者

提供抖音模块的帮助信息，包括基础命令、调试命令和使用示例。

作者: Assistant
创建时间: 2024年
"""

from services.common.help_provider import ModuleHelpProvider
from services.common.help_manager import get_help_manager


class DouyinHelpProvider(ModuleHelpProvider):
    """抖音模块帮助信息提供者"""

    def get_module_name(self) -> str:
        """获取模块显示名称"""
        return "抖音订阅"

    def get_basic_commands(self) -> str:
        """获取基础命令帮助信息"""
        return (
            "• /douyin_add <抖音链接> <频道ID> - 添加抖音订阅\n"
            "• /douyin_del <抖音链接> <频道ID> - 删除抖音订阅\n"
            "• /douyin_list [频道ID] - 查看订阅列表"
        )

    def get_debug_commands(self) -> str:
        """获取调试命令帮助信息"""
        return (
            "• /douyin_debug_show <JSON数据> - 调试抖音内容格式化\n"
            "• /douyin_debug_format <JSON数据> - 仅测试格式化\n"
            "• /douyin_debug_url <抖音链接> - 通过链接调试\n"
            "• /douyin_debug_sample [type] - 获取样例数据\n"
            "• /douyin_debug_file [type] - 获取样例文件"
        )

    def get_examples(self) -> str:
        """获取使用示例"""
        return (
            "• /douyin_add https://v.douyin.com/iM5g7LsM/ @channel\n"
            "• /douyin_add https://www.douyin.com/user/xxx -1001234567890\n"
            "• /douyin_list"
        )

    def get_description(self) -> str:
        """获取模块功能描述"""
        return "   • 支持抖音用户订阅，自动推送新发布内容"

    def get_order_priority(self) -> int:
        """获取显示顺序优先级"""
        return 20  # 抖音排在第二位


def register_help_provider():
    """注册抖音帮助信息提供者"""
    provider = DouyinHelpProvider()
    get_help_manager().register_provider("douyin", provider) 