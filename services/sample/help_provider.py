"""
Sample模块帮助信息提供者

提供Sample模块的帮助信息，包括基础命令、调试命令和使用示例。
支持样本账号订阅的完整帮助文档。

主要功能：
1. 动态命令名称生成（基于模块配置自动生成）
2. 完整的帮助文档

作者: Assistant
创建时间: 2024年
"""

from services.common.help_provider import ModuleHelpProvider
from services.common.help_manager import get_help_manager
from . import MODULE_DISPLAY_NAME, get_command_names


class SampleHelpProvider(ModuleHelpProvider):
    """Sample模块帮助信息提供者"""

    def get_module_name(self) -> str:
        """获取模块显示名称"""
        return MODULE_DISPLAY_NAME

    def get_basic_commands(self) -> str:
        """获取基础命令帮助信息（使用动态生成的命令名称）"""
        command_names = get_command_names()
        return (
            f"• /{command_names['add']} <样本链接> <频道ID> - 添加样本账号订阅\n"
            f"• /{command_names['del']} <样本链接> <频道ID> - 删除样本账号订阅\n"
            f"• /{command_names['list']} [频道ID] - 查看订阅列表"
        )

    def get_debug_commands(self) -> str:
        """获取调试命令帮助信息（使用动态生成的命令名称）"""
        command_names = get_command_names()
        return (
            f"• /{command_names['debug_show']} <样本链接> - 显示单个样本内容项"
        )

    def get_examples(self) -> str:
        """获取使用示例（使用动态生成的命令名称）"""
        command_names = get_command_names()
        return (
            f"• /{command_names['add']} https://www.sample.com/user/MS4wLjABAAAA... @mychannel\n"
            f"• /{command_names['add']} https://v.sample.com/iM5g7LsM/ -1001234567890\n"
            f"• /{command_names['list']} @mychannel\n"
            f"• /{command_names['del']} https://www.sample.com/user/MS4wLjABAAAA... @mychannel"
        )

    def get_description(self) -> str:
        """获取模块功能描述"""
        return "   • 支持样本账号订阅，自动推送最新视频和动态"

    def get_order_priority(self) -> int:
        """获取显示顺序优先级"""
        return 35  # 在douyin1(25)之后，rss(30)之前


def register_help_provider():
    """注册Sample帮助信息提供者"""
    from . import MODULE_NAME
    provider = SampleHelpProvider()
    get_help_manager().register_provider(MODULE_NAME, provider) 