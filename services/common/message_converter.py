"""
消息转换器基类模块

该模块定义了统一的消息转换接口，所有数据源模块（douyin、rsshub、rss等）都需要
实现MessageConverter接口，将自己的数据格式转换为统一的TelegramMessage格式。

这是实现"统一消息架构"的核心组件，确保不同数据源都能输出标准化的消息格式。

主要功能：
1. 定义统一的消息转换接口
2. 提供转换器注册和管理机制
3. 支持转换器的动态扩展
4. 提供转换过程的错误处理和日志记录
5. 支持转换器的配置和定制

作者: Assistant
创建时间: 2024年
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from enum import Enum

from .telegram_message import TelegramMessage, MediaItem, MediaType, ParseMode


class ConverterType(Enum):
    """转换器类型枚举"""
    DOUYIN = "douyin"
    RSSHUB = "rsshub"
    RSS = "rss"
    GENERIC = "generic"


class ConversionError(Exception):
    """转换过程中的异常"""
    def __init__(self, message: str, source_data: Any = None, converter_type: str = None):
        super().__init__(message)
        self.source_data = source_data
        self.converter_type = converter_type


class MessageConverter(ABC):
    """
    消息转换器基类

    所有数据源模块都需要继承此类并实现convert方法，
    将自己的数据格式转换为统一的TelegramMessage格式。
    """

    def __init__(self, converter_type: ConverterType):
        """
        初始化消息转换器

        Args:
            converter_type: 转换器类型
        """
        self.converter_type = converter_type
        self.logger = logging.getLogger(f"{__name__}.{converter_type.value}")

    @abstractmethod
    def convert(self, source_data: Any, **kwargs) -> TelegramMessage:
        """
        将源数据转换为TelegramMessage格式

        Args:
            source_data: 源数据（各模块的原始数据格式）
            **kwargs: 额外的转换参数

        Returns:
            TelegramMessage: 统一的Telegram消息格式

        Raises:
            ConversionError: 转换失败时抛出
        """
        pass

    @abstractmethod
    def convert_batch(self, source_data_list: List[Any], **kwargs) -> List[TelegramMessage]:
        """
        批量转换源数据为TelegramMessage格式

        Args:
            source_data_list: 源数据列表
            **kwargs: 额外的转换参数

        Returns:
            List[TelegramMessage]: 转换后的消息列表
        """
        pass

    def validate_source_data(self, source_data: Any) -> bool:
        """
        验证源数据的有效性

        Args:
            source_data: 要验证的源数据

        Returns:
            bool: 数据是否有效
        """
        try:
            return source_data is not None
        except Exception as e:
            self.logger.error(f"验证源数据失败: {str(e)}", exc_info=True)
            return False

    def extract_media_items(self, source_data: Any) -> List[MediaItem]:
        """
        从源数据中提取媒体项（子类可重写）

        Args:
            source_data: 源数据

        Returns:
            List[MediaItem]: 提取的媒体项列表
        """
        return []

    def format_text_content(self, source_data: Any) -> str:
        """
        格式化文本内容（子类可重写）

        Args:
            source_data: 源数据

        Returns:
            str: 格式化后的文本内容
        """
        return str(source_data)

    def get_parse_mode(self, source_data: Any) -> ParseMode:
        """
        获取解析模式（子类可重写）

        Args:
            source_data: 源数据

        Returns:
            ParseMode: 解析模式
        """
        return ParseMode.MARKDOWN_V2

    def handle_conversion_error(self, error: Exception, source_data: Any) -> Optional[TelegramMessage]:
        """
        处理转换错误（子类可重写）

        Args:
            error: 转换过程中的异常
            source_data: 导致错误的源数据

        Returns:
            Optional[TelegramMessage]: 降级处理后的消息，如果无法处理则返回None
        """
        self.logger.error(f"转换失败: {str(error)}", exc_info=True)

        # 默认降级策略：创建纯文本消息
        try:
            fallback_text = f"内容转换失败: {str(source_data)[:100]}..."
            return TelegramMessage.create_text_message(
                text=fallback_text,
                parse_mode=ParseMode.NONE
            )
        except Exception as fallback_error:
            self.logger.error(f"降级处理也失败: {str(fallback_error)}", exc_info=True)
            return None


class ConverterRegistry:
    """
    转换器注册表

    管理所有已注册的消息转换器，提供转换器的注册、获取和管理功能。
    """

    def __init__(self):
        """初始化转换器注册表"""
        self._converters: Dict[ConverterType, MessageConverter] = {}
        self.logger = logging.getLogger(__name__)

    def register(self, converter: MessageConverter) -> None:
        """
        注册消息转换器

        Args:
            converter: 要注册的转换器实例
        """
        try:
            self._converters[converter.converter_type] = converter
            self.logger.info(f"注册转换器: {converter.converter_type.value}")
        except Exception as e:
            self.logger.error(f"注册转换器失败: {str(e)}", exc_info=True)
            raise

    def get_converter(self, converter_type: ConverterType) -> Optional[MessageConverter]:
        """
        获取指定类型的转换器

        Args:
            converter_type: 转换器类型

        Returns:
            Optional[MessageConverter]: 转换器实例，如果不存在则返回None
        """
        return self._converters.get(converter_type)

    def unregister(self, converter_type: ConverterType) -> bool:
        """
        注销指定类型的转换器

        Args:
            converter_type: 要注销的转换器类型

        Returns:
            bool: 是否成功注销
        """
        try:
            if converter_type in self._converters:
                del self._converters[converter_type]
                self.logger.info(f"注销转换器: {converter_type.value}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"注销转换器失败: {str(e)}", exc_info=True)
            return False

    def list_converters(self) -> List[ConverterType]:
        """
        列出所有已注册的转换器类型

        Returns:
            List[ConverterType]: 已注册的转换器类型列表
        """
        return list(self._converters.keys())

    def convert_with_type(
        self,
        converter_type: ConverterType,
        source_data: Any,
        **kwargs
    ) -> Optional[TelegramMessage]:
        """
        使用指定类型的转换器进行转换

        Args:
            converter_type: 转换器类型
            source_data: 源数据
            **kwargs: 额外的转换参数

        Returns:
            Optional[TelegramMessage]: 转换后的消息，失败时返回None
        """
        try:
            converter = self.get_converter(converter_type)
            if not converter:
                self.logger.error(f"转换器不存在: {converter_type.value}")
                return None

            return converter.convert(source_data, **kwargs)
        except Exception as e:
            self.logger.error(f"转换失败: {str(e)}", exc_info=True)
            return None


# 全局转换器注册表实例
_global_registry = ConverterRegistry()


def register_converter(converter: MessageConverter) -> None:
    """
    注册转换器到全局注册表

    Args:
        converter: 要注册的转换器实例
    """
    _global_registry.register(converter)


def get_converter(converter_type: ConverterType) -> Optional[MessageConverter]:
    """
    从全局注册表获取转换器

    Args:
        converter_type: 转换器类型

    Returns:
        Optional[MessageConverter]: 转换器实例
    """
    return _global_registry.get_converter(converter_type)


def convert_message(
    converter_type: ConverterType,
    source_data: Any,
    **kwargs
) -> Optional[TelegramMessage]:
    """
    使用全局注册表进行消息转换

    Args:
        converter_type: 转换器类型
        source_data: 源数据
        **kwargs: 额外的转换参数

    Returns:
        Optional[TelegramMessage]: 转换后的消息
    """
    return _global_registry.convert_with_type(converter_type, source_data, **kwargs)


def list_available_converters() -> List[ConverterType]:
    """
    列出所有可用的转换器类型

    Returns:
        List[ConverterType]: 可用的转换器类型列表
    """
    return _global_registry.list_converters()


class GenericConverter(MessageConverter):
    """
    通用转换器实现

    提供基本的转换功能，可以处理简单的数据格式。
    主要用于测试和作为其他转换器的参考实现。
    """

    def __init__(self):
        """初始化通用转换器"""
        super().__init__(ConverterType.GENERIC)

    def convert(self, source_data: Any, **kwargs) -> TelegramMessage:
        """
        转换源数据为TelegramMessage

        Args:
            source_data: 源数据
            **kwargs: 额外参数

        Returns:
            TelegramMessage: 转换后的消息
        """
        try:
            if not self.validate_source_data(source_data):
                raise ConversionError("源数据无效", source_data, self.converter_type.value)

            # 处理字典格式的数据
            if isinstance(source_data, dict):
                return self._convert_dict_data(source_data, **kwargs)

            # 处理字符串数据
            elif isinstance(source_data, str):
                return TelegramMessage.create_text_message(
                    text=source_data,
                    parse_mode=self.get_parse_mode(source_data)
                )

            # 其他类型转为字符串处理
            else:
                text_content = self.format_text_content(source_data)
                return TelegramMessage.create_text_message(
                    text=text_content,
                    parse_mode=ParseMode.NONE
                )

        except Exception as e:
            if isinstance(e, ConversionError):
                raise
            else:
                raise ConversionError(f"转换失败: {str(e)}", source_data, self.converter_type.value)

    def convert_batch(self, source_data_list: List[Any], **kwargs) -> List[TelegramMessage]:
        """
        批量转换源数据

        Args:
            source_data_list: 源数据列表
            **kwargs: 额外参数

        Returns:
            List[TelegramMessage]: 转换后的消息列表
        """
        messages = []
        for i, source_data in enumerate(source_data_list):
            try:
                message = self.convert(source_data, **kwargs)
                messages.append(message)
            except Exception as e:
                self.logger.error(f"批量转换第{i+1}项失败: {str(e)}", exc_info=True)
                # 尝试降级处理
                fallback_message = self.handle_conversion_error(e, source_data)
                if fallback_message:
                    messages.append(fallback_message)

        return messages

    def _convert_dict_data(self, data: Dict[str, Any], **kwargs) -> TelegramMessage:
        """
        转换字典格式的数据

        Args:
            data: 字典数据
            **kwargs: 额外参数

        Returns:
            TelegramMessage: 转换后的消息
        """
        # 提取文本内容
        text = data.get('text', data.get('content', data.get('title', str(data))))

        # 提取媒体项
        media_items = self.extract_media_items(data)

        # 创建消息
        if media_items:
            return TelegramMessage.create_media_group_message(
                media_group=media_items,
                caption=text,
                parse_mode=self.get_parse_mode(data)
            )
        else:
            return TelegramMessage.create_text_message(
                text=text,
                parse_mode=self.get_parse_mode(data)
            )

    def extract_media_items(self, source_data: Any) -> List[MediaItem]:
        """
        从源数据中提取媒体项

        Args:
            source_data: 源数据

        Returns:
            List[MediaItem]: 媒体项列表
        """
        media_items = []

        if isinstance(source_data, dict):
            # 处理单个媒体URL
            if 'media_url' in source_data:
                media_type = self._detect_media_type(source_data['media_url'])
                media_items.append(MediaItem(
                    type=media_type,
                    url=source_data['media_url']
                ))

            # 处理媒体列表
            elif 'media_list' in source_data:
                for media_url in source_data['media_list']:
                    media_type = self._detect_media_type(media_url)
                    media_items.append(MediaItem(
                        type=media_type,
                        url=media_url
                    ))

        return media_items

    def _detect_media_type(self, url: str) -> MediaType:
        """
        根据URL检测媒体类型

        Args:
            url: 媒体URL

        Returns:
            MediaType: 检测到的媒体类型
        """
        url_lower = url.lower()

        if any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            return MediaType.PHOTO
        elif any(ext in url_lower for ext in ['.mp4', '.avi', '.mov', '.webm']):
            return MediaType.VIDEO
        elif any(ext in url_lower for ext in ['.mp3', '.wav', '.ogg']):
            return MediaType.AUDIO
        else:
            return MediaType.DOCUMENT


if __name__ == "__main__":
    # 模块测试代码
    import asyncio

    def test_message_converter():
        """测试消息转换器功能"""
        print("🧪 消息转换器模块测试")

        # 测试通用转换器
        converter = GenericConverter()
        print(f"✅ 创建通用转换器: {converter.converter_type.value}")

        # 测试字符串转换
        text_message = converter.convert("这是一条测试消息")
        print(f"✅ 字符串转换: {text_message.text[:20]}...")

        # 测试字典转换
        dict_data = {
            'title': '测试标题',
            'content': '测试内容',
            'media_url': 'https://example.com/image.jpg'
        }
        dict_message = converter.convert(dict_data)
        print(f"✅ 字典转换: 媒体组={len(dict_message.media_group)}个")

        # 测试批量转换
        batch_data = ["消息1", "消息2", {"title": "消息3"}]
        batch_messages = converter.convert_batch(batch_data)
        print(f"✅ 批量转换: {len(batch_messages)}条消息")

        # 测试转换器注册
        register_converter(converter)
        registered_converters = list_available_converters()
        print(f"✅ 转换器注册: {len(registered_converters)}个已注册")

        # 测试全局转换
        global_message = convert_message(ConverterType.GENERIC, "全局转换测试")
        print(f"✅ 全局转换: {global_message.text[:20]}...")

        print("🎉 消息转换器模块测试完成")

    # 运行测试
    test_message_converter()