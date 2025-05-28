"""
帮助信息管理器

负责收集、组织和生成所有模块的帮助信息，提供统一的帮助信息管理接口。

作者: Assistant
创建时间: 2024年
"""

import logging
from typing import Dict, List
from .help_provider import ModuleHelpProvider


class HelpManager:
    """
    帮助信息管理器

    负责注册和管理所有模块的帮助信息提供者，生成统一的帮助文档
    """

    def __init__(self):
        """初始化帮助管理器"""
        self.providers: Dict[str, ModuleHelpProvider] = {}
        self.logger = logging.getLogger("help_manager")
        self.logger.info("帮助信息管理器初始化完成")

    def register_provider(self, module_name: str, provider: ModuleHelpProvider) -> None:
        """
        注册模块帮助信息提供者

        Args:
            module_name: 模块名称（如'douyin', 'rsshub'）
            provider: 帮助信息提供者实例
        """
        if not isinstance(provider, ModuleHelpProvider):
            raise TypeError(f"提供者必须是ModuleHelpProvider的实例，收到: {type(provider)}")

        self.providers[module_name] = provider
        self.logger.info(f"✅ 注册模块帮助信息: {module_name} -> {provider.get_module_name()}")

    def get_registered_modules(self) -> List[str]:
        """
        获取已注册的模块列表

        Returns:
            List[str]: 已注册的模块名称列表
        """
        return list(self.providers.keys())

    def generate_full_help(self, debug_enabled: bool = False) -> str:
        """
        生成完整的帮助信息

        Args:
            debug_enabled: 是否启用调试模式，决定是否显示调试命令

        Returns:
            str: 完整的帮助信息文本
        """
        self.logger.info(f"🔄 生成帮助信息，调试模式: {debug_enabled}, 已注册模块: {len(self.providers)}")

        # 基础帮助头部
        help_text = (
            "🤖 Any RSS Bot - RSS订阅机器人\n\n"
            "自动监控RSS源并推送新内容到Telegram频道。\n\n"
        )

        # 按优先级排序模块
        sorted_providers = sorted(
            self.providers.items(),
            key=lambda x: x[1].get_order_priority()
        )

        # 生成各模块的帮助信息
        for module_name, provider in sorted_providers:
            try:
                help_text += self._generate_module_help(provider, debug_enabled)
            except Exception as e:
                self.logger.error(f"❌ 生成模块帮助信息失败: {module_name}, 错误: {str(e)}", exc_info=True)
                # 继续处理其他模块，不因单个模块错误而中断

        # 添加通用帮助信息
        help_text += self._generate_common_help()

        self.logger.info(f"✅ 帮助信息生成完成，总长度: {len(help_text)} 字符")
        return help_text

    def _generate_module_help(self, provider: ModuleHelpProvider, debug_enabled: bool) -> str:
        """
        生成单个模块的帮助信息

        Args:
            provider: 模块帮助信息提供者
            debug_enabled: 是否启用调试模式

        Returns:
            str: 模块帮助信息文本
        """
        module_help = f"📱 **{provider.get_module_name()}**\n"

        # 添加模块描述（如果有）
        description = provider.get_description()
        if description:
            module_help += f"{description}\n"

        # 添加基础命令
        basic_commands = provider.get_basic_commands()
        if basic_commands:
            module_help += f"{basic_commands}\n"

        # 添加调试命令（仅在调试模式下）
        if debug_enabled:
            debug_commands = provider.get_debug_commands()
            if debug_commands:
                module_help += f"\n🔧 调试命令：\n{debug_commands}\n"

        # 添加使用示例（如果有）
        examples = provider.get_examples()
        if examples:
            module_help += f"\n💡 使用示例：\n{examples}\n"

        module_help += "\n"
        return module_help

    def _generate_common_help(self) -> str:
        """
        生成通用帮助信息

        Returns:
            str: 通用帮助信息文本
        """
        return (
            "• /help - 显示此帮助信息\n\n"
            "📝 使用说明：\n"
            "• 频道ID格式：@channel_name 或 -100xxxxxxxxx\n"
            "• 订阅前确保机器人已加入目标频道\n"
            "• 每小时自动检查并推送新内容"
        )


# 全局帮助管理器实例
_help_manager = None


def get_help_manager() -> HelpManager:
    """
    获取全局帮助管理器实例（单例模式）

    Returns:
        HelpManager: 帮助管理器实例
    """
    global _help_manager
    if _help_manager is None:
        _help_manager = HelpManager()
    return _help_manager