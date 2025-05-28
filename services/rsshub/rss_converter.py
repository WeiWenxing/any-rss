"""
RSS消息转换器模块

该模块实现MessageConverter接口，将RSSEntry转换为统一的TelegramMessage格式。
支持智能媒体处理和消息格式化，确保RSS内容在Telegram中的最佳展示效果。

主要功能：
1. RSSEntry到TelegramMessage的转换
2. 智能媒体策略选择（媒体组/文本预览/纯文本）
3. 消息文本的格式化和优化
4. 媒体附件的处理和验证
5. 链接预览的智能控制

作者: Assistant
创建时间: 2024年
"""

import logging
import re
from typing import List, Optional
from urllib.parse import urlparse

from services.common.message_converter import MessageConverter, ConversionError, ConverterType, register_converter
from services.common.telegram_message import TelegramMessage, MediaItem
from .rss_entry import RSSEntry, RSSEnclosure


class RSSMessageConverter(MessageConverter):
    """
    RSS消息转换器

    将RSSEntry转换为统一的TelegramMessage格式，实现统一消息架构
    """

    def __init__(self, max_text_length: int = 4000, max_media_items: int = 10):
        """
        初始化RSS消息转换器

        Args:
            max_text_length: 最大文本长度
            max_media_items: 最大媒体项数量
        """
        super().__init__(ConverterType.RSSHUB)
        self.max_text_length = max_text_length
        self.max_media_items = max_media_items

        self.logger.info(f"RSS消息转换器初始化完成，最大文本长度: {max_text_length}, 最大媒体数: {max_media_items}")

    def convert(self, source_data, **kwargs) -> TelegramMessage:
        """
        实现MessageConverter接口的convert方法

        Args:
            source_data: RSS条目对象或字典格式的内容数据
            **kwargs: 额外参数

        Returns:
            TelegramMessage: 转换后的消息
        """
        # 如果是RSSEntry对象，直接转换
        if isinstance(source_data, RSSEntry):
            return self.to_telegram_message(source_data)

        # 如果是字典格式，先转换为RSSEntry对象
        elif isinstance(source_data, dict):
            rss_entry = self._dict_to_rss_entry(source_data)
            return self.to_telegram_message(rss_entry)

        else:
            raise ConversionError(f"不支持的数据类型: {type(source_data)}")

    def convert_batch(self, source_data_list: List[RSSEntry], **kwargs) -> List[TelegramMessage]:
        """
        实现MessageConverter接口的convert_batch方法

        Args:
            source_data_list: RSS条目列表
            **kwargs: 额外参数

        Returns:
            List[TelegramMessage]: 转换后的消息列表
        """
        messages = []
        for entry in source_data_list:
            try:
                message = self.to_telegram_message(entry)
                messages.append(message)
            except Exception as e:
                self.logger.error(f"批量转换RSS条目失败: {entry.item_id}, 错误: {str(e)}", exc_info=True)
                # 尝试降级处理
                fallback_message = self.handle_conversion_error(e, entry)
                if fallback_message:
                    messages.append(fallback_message)
        return messages

    def to_telegram_message(self, rss_entry: RSSEntry) -> TelegramMessage:
        """
        将RSS条目转换为Telegram消息

        Args:
            rss_entry: RSS条目对象

        Returns:
            TelegramMessage: 统一的Telegram消息格式

        Raises:
            ConversionError: 转换失败时抛出异常
        """
        try:
            self.logger.debug(f"开始转换RSS条目: {rss_entry.item_id}")

            # 1. 提取和处理媒体项
            media_items = self._extract_media_items(rss_entry)

            # 2. 决定发送策略
            send_strategy = self._determine_send_strategy(media_items)

            # 3. 格式化消息文本
            message_text = self._format_message_text(rss_entry, send_strategy)

            # 4. 构建TelegramMessage对象
            telegram_message = self._build_telegram_message(
                message_text, media_items, send_strategy
            )

            self.logger.debug(f"RSS条目转换完成: {rss_entry.item_id}, 策略: {send_strategy}")
            return telegram_message

        except Exception as e:
            error_msg = f"RSS条目转换失败: {rss_entry.item_id}, 错误: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ConversionError(error_msg)

    def _dict_to_rss_entry(self, content_data: dict) -> RSSEntry:
        """
        将字典格式的内容数据转换为RSSEntry对象

        Args:
            content_data: 字典格式的内容数据

        Returns:
            RSSEntry: RSS条目对象
        """
        try:
            from .rss_entry import create_rss_entry
            from datetime import datetime

            # 提取基本信息
            title = content_data.get('title', '无标题')
            link = content_data.get('link', '')
            description = content_data.get('description', '')
            author = content_data.get('author', '')

            # 处理时间字段
            published_time = None
            if content_data.get('published'):
                try:
                    if isinstance(content_data['published'], str):
                        # 如果是ISO格式字符串，尝试解析
                        published_time = datetime.fromisoformat(content_data['published'].replace('Z', '+00:00'))
                    elif isinstance(content_data['published'], datetime):
                        published_time = content_data['published']
                except Exception as e:
                    self.logger.warning(f"解析发布时间失败: {content_data.get('published')}, 错误: {str(e)}")

            # 创建RSSEntry对象
            rss_entry = create_rss_entry(
                title=title,
                link=link,
                description=description,
                author=author,
                published=published_time,
                guid=content_data.get('item_id')  # 使用item_id作为guid
            )

            # 添加媒体附件（如果有的话）
            enclosures = content_data.get('enclosures', [])
            for enc_data in enclosures:
                if isinstance(enc_data, dict):
                    rss_entry.add_enclosure(
                        url=enc_data.get('url', ''),
                        mime_type=enc_data.get('type', ''),
                        length=enc_data.get('length', 0)
                    )

            return rss_entry

        except Exception as e:
            error_msg = f"字典转RSSEntry失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ConversionError(error_msg)

    def _extract_media_items(self, rss_entry: RSSEntry) -> List[MediaItem]:
        """
        从RSS条目中提取媒体项

        Args:
            rss_entry: RSS条目对象

        Returns:
            List[MediaItem]: 媒体项列表
        """
        media_items = []

        try:
            # 直接使用RSSParser已经解析好的所有媒体附件
            for enclosure in rss_entry.enclosures:
                media_item = self._convert_enclosure_to_media_item(enclosure, rss_entry)
                if media_item:
                    media_items.append(media_item)

                    # 限制媒体数量
                    if len(media_items) >= self.max_media_items:
                        self.logger.debug(f"达到最大媒体数量限制: {self.max_media_items}")
                        break

            self.logger.debug(f"提取到 {len(media_items)} 个媒体项")
            return media_items

        except Exception as e:
            self.logger.warning(f"提取媒体项失败: {str(e)}")
            return []

    def _convert_enclosure_to_media_item(self, enclosure: RSSEnclosure, rss_entry: RSSEntry) -> Optional[MediaItem]:
        """
        将RSS enclosure转换为MediaItem

        Args:
            enclosure: RSS媒体附件
            rss_entry: RSS条目对象

        Returns:
            Optional[MediaItem]: 媒体项，转换失败返回None
        """
        try:
            # 确定媒体类型
            media_type = self._determine_media_type(enclosure.type)
            if not media_type:
                return None

            # 验证URL
            if not self._is_valid_media_url(enclosure.url):
                return None

            # 转换为绝对URL
            absolute_url = rss_entry.get_absolute_url(enclosure.url)

            # 处理视频封面图
            thumbnail_url = None
            if media_type == "video" and enclosure.poster:
                # 转换poster为绝对URL
                thumbnail_url = rss_entry.get_absolute_url(enclosure.poster)
                # 验证poster URL
                if not self._is_valid_media_url(thumbnail_url):
                    self.logger.debug(f"视频封面URL无效: {thumbnail_url}")
                    thumbnail_url = None
                else:
                    self.logger.debug(f"视频封面URL有效: {thumbnail_url}")

            # 创建MediaItem
            media_item = MediaItem(
                type=media_type,
                url=absolute_url,
                caption=rss_entry.title if len(rss_entry.enclosures) == 1 else None,
                thumbnail_url=thumbnail_url  # 传递poster信息
            )

            return media_item

        except Exception as e:
            self.logger.warning(f"转换enclosure失败: {enclosure.url}, 错误: {str(e)}")
            return None

    def _determine_media_type(self, mime_type: str) -> Optional[str]:
        """
        根据MIME类型确定媒体类型

        Args:
            mime_type: MIME类型

        Returns:
            Optional[str]: 媒体类型字符串，不支持的类型返回None
        """
        if not mime_type:
            return None

        mime_type = mime_type.lower()

        if mime_type.startswith('image/'):
            return "photo"
        elif mime_type.startswith('video/'):
            return "video"
        elif mime_type.startswith('audio/'):
            return "audio"
        elif mime_type in ['application/pdf', 'application/zip', 'application/rar']:
            return "document"
        else:
            return None

    def _is_valid_media_url(self, url: str) -> bool:
        """
        验证媒体URL是否有效

        Args:
            url: 媒体URL

        Returns:
            bool: 是否有效
        """
        try:
            if not url:
                return False

            # 基础URL格式验证
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False

            # 检查协议
            if parsed.scheme not in ['http', 'https']:
                return False

            # 检查文件扩展名（可选）
            path = parsed.path.lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.avi', '.mov', '.mp3', '.wav', '.pdf']

            # 如果有扩展名，检查是否支持
            if '.' in path:
                extension = '.' + path.split('.')[-1]
                if extension not in valid_extensions:
                    return False

            return True

        except Exception:
            return False

    def _determine_send_strategy(self, media_items: List[MediaItem]) -> str:
        """
        决定发送策略

        Args:
            media_items: 媒体项列表

        Returns:
            str: 发送策略 ("media_group", "text_with_preview", "text_only")
        """
        media_count = len(media_items)

        if media_count >= 1:
            return "media_group"  # 有媒体就使用媒体组模式
        else:
            return "text_only"  # 无媒体使用纯文本模式

    def _format_message_text(self, rss_entry: RSSEntry, send_strategy: str) -> str:
        """
        根据发送策略格式化消息文本

        Args:
            rss_entry: RSS条目对象
            send_strategy: 发送策略

        Returns:
            str: 格式化后的消息文本
        """
        try:
            message_parts = []

            if send_strategy == "media_group":
                # 媒体组模式：简洁文本
                message_parts.append(f"📰 **{rss_entry.title}**")

                if rss_entry.author:
                    message_parts.append(f"👤 {rss_entry.author}")

                if rss_entry.effective_published_time:
                    time_str = rss_entry.effective_published_time.strftime("%Y-%m-%d %H:%M")
                    message_parts.append(f"⏰ {time_str}")

                if rss_entry.link:
                    message_parts.append(f"🔗 [查看原文]({rss_entry.link})")

            else:
                # 文本模式：完整内容
                message_parts.append(f"📰 **{rss_entry.title}**")

                # 添加描述或内容摘要
                content = rss_entry.effective_content
                if content:
                    # 限制内容长度
                    max_content_length = self.max_text_length - 500  # 预留空间给其他信息
                    if len(content) > max_content_length:
                        content = content[:max_content_length] + "..."

                    message_parts.append(f"\n{content}")

                # 添加元信息
                meta_parts = []
                if rss_entry.effective_published_time:
                    time_str = rss_entry.effective_published_time.strftime("%Y-%m-%d %H:%M")
                    meta_parts.append(f"⏰ {time_str}")

                if rss_entry.author:
                    meta_parts.append(f"👤 {rss_entry.author}")

                if rss_entry.category:
                    meta_parts.append(f"🏷️ {rss_entry.category}")

                if meta_parts:
                    message_parts.append(f"\n{' | '.join(meta_parts)}")

                if rss_entry.link:
                    message_parts.append(f"\n🔗 [查看原文]({rss_entry.link})")

            # 组合消息文本
            message_text = "\n".join(message_parts)

            # 确保不超过最大长度
            if len(message_text) > self.max_text_length:
                message_text = message_text[:self.max_text_length-3] + "..."

            return message_text

        except Exception as e:
            self.logger.error(f"格式化消息文本失败: {str(e)}", exc_info=True)
            # 返回基础格式
            return f"📰 {rss_entry.title}\n🔗 {rss_entry.link}"

    def _build_telegram_message(
        self,
        message_text: str,
        media_items: List[MediaItem],
        send_strategy: str
    ) -> TelegramMessage:
        """
        构建TelegramMessage对象

        Args:
            message_text: 消息文本
            media_items: 媒体项列表
            send_strategy: 发送策略

        Returns:
            TelegramMessage: 统一的Telegram消息对象
        """
        try:
            if send_strategy == "media_group":
                # 媒体组模式
                return TelegramMessage(
                    text=message_text,
                    media_group=media_items,
                    parse_mode="Markdown",
                    disable_web_page_preview=True  # 媒体组模式禁用链接预览
                )
            elif send_strategy == "text_with_preview":
                # 文本+预览模式（不发送媒体组，启用链接预览）
                return TelegramMessage(
                    text=message_text,
                    media_group=[],  # 不使用媒体组
                    parse_mode="Markdown",
                    disable_web_page_preview=False  # 启用链接预览
                )
            else:
                # 纯文本模式
                return TelegramMessage(
                    text=message_text,
                    media_group=[],
                    parse_mode="Markdown",
                    disable_web_page_preview=False  # 启用链接预览作为补偿
                )

        except Exception as e:
            self.logger.error(f"构建TelegramMessage失败: {str(e)}", exc_info=True)
            # 返回基础消息
            return TelegramMessage(
                text=message_text,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )

    def get_converter_info(self) -> dict:
        """
        获取转换器信息

        Returns:
            dict: 转换器信息
        """
        return {
            'name': 'RSSMessageConverter',
            'version': '1.0.0',
            'source_type': 'RSSEntry',
            'target_type': 'TelegramMessage',
            'max_text_length': self.max_text_length,
            'max_media_items': self.max_media_items,
            'supported_strategies': ['media_group', 'text_with_preview', 'text_only']
        }


# 便捷函数：创建RSS消息转换器实例
def create_rss_converter(max_text_length: int = 4000, max_media_items: int = 10) -> RSSMessageConverter:
    """
    创建RSS消息转换器实例

    Args:
        max_text_length: 最大文本长度
        max_media_items: 最大媒体项数量

    Returns:
        RSSMessageConverter: RSS消息转换器实例
    """
    converter = RSSMessageConverter(max_text_length, max_media_items)

    # 自动注册到全局转换器注册表
    try:
        register_converter(converter)
    except Exception as e:
        converter.logger.warning(f"注册RSS转换器失败: {str(e)}")

    return converter


# 便捷函数：快速转换RSS条目
def convert_rss_entry(rss_entry: RSSEntry) -> TelegramMessage:
    """
    快速转换RSS条目的便捷函数

    Args:
        rss_entry: RSS条目对象

    Returns:
        TelegramMessage: 转换后的Telegram消息
    """
    converter = create_rss_converter()
    return converter.to_telegram_message(rss_entry)


if __name__ == "__main__":
    # 模块测试代码
    from datetime import datetime
    from .rss_entry import create_rss_entry

    def test_rss_converter():
        """测试RSS消息转换器功能"""
        print("🧪 RSS消息转换器模块测试")

        # 创建转换器
        converter = create_rss_converter()
        print(f"✅ 创建RSS转换器: {type(converter).__name__}")

        # 创建测试RSS条目
        test_entry = create_rss_entry(
            title="测试RSS条目标题",
            link="https://example.com/article/1",
            description="这是一个测试RSS条目的描述内容，用于验证转换器的功能。",
            author="测试作者",
            published=datetime.now()
        )

        # 添加媒体附件
        test_entry.add_enclosure("https://example.com/image1.jpg", "image/jpeg", 1024000)
        test_entry.add_enclosure("https://example.com/image2.png", "image/png", 512000)

        print(f"✅ 创建测试RSS条目: {test_entry.item_id}")

        # 测试转换
        telegram_message = converter.to_telegram_message(test_entry)
        print(f"✅ 转换为Telegram消息: {len(telegram_message.text)}字符")
        print(f"✅ 媒体组数量: {len(telegram_message.media_group)}个")
        print(f"✅ 解析模式: {telegram_message.parse_mode}")

        # 测试转换器信息
        converter_info = converter.get_converter_info()
        print(f"✅ 转换器信息: {converter_info['name']} v{converter_info['version']}")

        print("🎉 RSS消息转换器模块测试完成")

    # 运行测试
    test_rss_converter()