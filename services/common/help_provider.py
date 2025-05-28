"""
帮助信息提供者基类

定义了模块帮助信息的标准接口，确保所有模块提供一致格式的帮助信息。

作者: Assistant
创建时间: 2024年
"""

from abc import ABC, abstractmethod
from typing import Optional


class ModuleHelpProvider(ABC):
    """
    模块帮助信息提供者基类

    每个模块需要实现此接口来提供自己的帮助信息
    """

    @abstractmethod
    def get_module_name(self) -> str:
        """
        获取模块显示名称

        Returns:
            str: 模块的中文显示名称，如"抖音订阅"、"RSS订阅"
        """
        pass

    @abstractmethod
    def get_basic_commands(self) -> str:
        """
        获取基础命令帮助信息

        Returns:
            str: 基础命令的帮助文本，包含命令名称、参数和说明
        """
        pass

    def get_debug_commands(self) -> Optional[str]:
        """
        获取调试命令帮助信息（可选）

        Returns:
            Optional[str]: 调试命令的帮助文本，如果没有调试命令则返回None
        """
        return None

    def get_examples(self) -> Optional[str]:
        """
        获取使用示例（可选）

        Returns:
            Optional[str]: 使用示例文本
        """
        return None

    def get_description(self) -> Optional[str]:
        """
        获取模块功能描述（可选）

        Returns:
            Optional[str]: 模块功能的详细描述
        """
        return None

    def get_order_priority(self) -> int:
        """
        获取显示顺序优先级

        Returns:
            int: 优先级数字，数字越小越靠前显示，默认为100
        """
        return 100