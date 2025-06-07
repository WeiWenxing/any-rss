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

    def __init__(self, max_text_length: int = 4000, max_media_items: int = 200):
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
            message_text, caption = self._format_message_text(rss_entry, send_strategy)

            # 4. 构建TelegramMessage对象
            telegram_message = self._build_telegram_message(
                message_text, media_items, send_strategy, caption
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

    def _format_message_text(self, rss_entry: RSSEntry, send_strategy: str) -> tuple[str, str]:
        """
        根据发送策略格式化消息文本和caption

        Args:
            rss_entry: RSS条目对象
            send_strategy: 发送策略

        Returns:
            tuple[str, str]: (完整消息文本, 简短caption)
        """
        try:
            # 1. 处理标题 - 使用Markdown粗体，截断到15个字符
            title = rss_entry.title or "无标题"
            if len(title) > 15:
                # 在词边界截断，避免破坏词汇
                truncated_title = title[:15]
                # 如果截断位置不是空格，向前找到最近的空格或标点
                if len(title) > 15 and title[15] not in [' ', '，', '。', '、', '；']:
                    for i in range(14, 0, -1):
                        if title[i] in [' ', '，', '。', '、', '；']:
                            truncated_title = title[:i]
                            break
                title = truncated_title + "..."

            # 2. 构建固定部分（除了内容摘要外的所有部分）
            fixed_parts = []

            # 标题部分
            title_part = f"*{title}*"
            fixed_parts.append(title_part)
            fixed_parts.append("")  # 标题后空行

            # 元信息部分
            meta_parts = []
            if rss_entry.author:
                meta_parts.append(f"Author: {rss_entry.author}")
            if rss_entry.effective_published_time:
                time_str = rss_entry.effective_published_time.strftime("%Y-%m-%d %H:%M")
                meta_parts.append(f"Date: {time_str}")
            if rss_entry.category:
                meta_parts.append(f"Category: {rss_entry.category}")

            meta_text = ""
            if meta_parts:
                meta_text = " | ".join(meta_parts)
                fixed_parts.append("")  # 内容后空行（为元信息预留）
                fixed_parts.append(meta_text)
                fixed_parts.append("")  # 元信息后空行

            # 链接部分
            link_part = ""
            if rss_entry.link:
                link_part = f"[查看原文]({rss_entry.link})"
                fixed_parts.append(link_part)

            # 3. 计算固定部分的总长度
            fixed_text = "\n".join(fixed_parts)
            fixed_length = len(fixed_text)

            # 4. 计算内容摘要的最大允许长度
            # 预留一些空间给内容后的空行和可能的截断标记
            content_space_overhead = 2  # 内容前后的空行 "\n\n"
            truncate_overhead = 3  # 可能的"..."
            max_content_length = self.max_text_length - fixed_length - content_space_overhead - truncate_overhead

            # 确保最大内容长度不为负数
            if max_content_length < 0:
                max_content_length = 0
                self.logger.warning(f"固定部分长度 {fixed_length} 超过最大文本长度 {self.max_text_length}")

            # 5. 处理内容摘要
            content = rss_entry.effective_content or ""
            if content and max_content_length > 0:
                if len(content) > max_content_length:
                    # 按句子边界截断
                    content = self._smart_truncate(content, max_content_length)
            elif max_content_length <= 0:
                content = ""  # 如果没有空间，不显示内容

            # 6. 组合最终的消息文本
            final_parts = []
            final_parts.append(title_part)
            final_parts.append("")  # 标题后空行

            if content:
                final_parts.append(content)
                final_parts.append("")  # 内容后空行

            if meta_text:
                final_parts.append(meta_text)
                final_parts.append("")  # 元信息后空行

            if link_part:
                final_parts.append(link_part)

            full_text = "\n".join(final_parts)

            # 7. 最终长度检查（防御性编程）
            if len(full_text) > self.max_text_length:
                self.logger.warning(f"文本长度 {len(full_text)} 仍超过限制 {self.max_text_length}，强制截断")
                full_text = full_text[:self.max_text_length-3] + "..."

            # 8. 生成caption
            if len(full_text) < 1000:
                caption = ""
            else:
                # 复用已计算的固定部分，只改变最大长度限制
                caption_max_length = 1000
                caption_overhead = 5  # 预留空间给可能的截断和空行
                caption_max_content_length = caption_max_length - fixed_length - caption_overhead

                # 如果有足够空间，添加部分内容到caption
                caption_parts = []
                caption_parts.append(title_part)
                caption_parts.append("")  # 标题后空行

                if content and caption_max_content_length > 50:  # 至少要有50字符才值得添加内容
                    # 截断内容用于caption
                    caption_content = self._smart_truncate(content, caption_max_content_length)
                    caption_parts.append(caption_content)
                    caption_parts.append("")  # 内容后空行

                if meta_text:
                    caption_parts.append(meta_text)
                    caption_parts.append("")  # 元信息后空行

                if link_part:
                    caption_parts.append(link_part)

                caption = "\n".join(caption_parts)

                # 最终长度检查
                if len(caption) > caption_max_length:
                    self.logger.warning(f"Caption长度 {len(caption)} 超过1024限制，强制截断")
                    caption = caption[:caption_max_length-3] + "..."

            self.logger.debug(f"文本长度控制: 固定部分={fixed_length}, 内容空间={max_content_length}, 最终长度={len(full_text)}")
            return full_text, caption

        except Exception as e:
            self.logger.error(f"格式化消息文本失败: {str(e)}", exc_info=True)
            # 返回基础格式
            title = rss_entry.title[:15] + "..." if len(rss_entry.title) > 15 else rss_entry.title
            fallback_text = f"*{title}*\n\n[查看原文]({rss_entry.link})"

            # 使用相同的caption生成策略
            if len(fallback_text) < 1000:
                fallback_caption = ""
            else:
                # 计算fallback caption的固定部分
                caption_title_part = f"*{title}*"
                caption_link_part = f"[查看原文]({rss_entry.link})" if rss_entry.link else ""

                # 简单的fallback caption（只包含标题和链接）
                if caption_link_part:
                    fallback_caption = f"{caption_title_part}\n\n{caption_link_part}"
                else:
                    fallback_caption = caption_title_part

                # 确保不超过1024字符
                if len(fallback_caption) > 1024:
                    fallback_caption = fallback_caption[:1021] + "..."

            return fallback_text, fallback_caption

    def _smart_truncate(self, text: str, max_length: int) -> str:
        """
        智能截断文本，在句子边界截断

        Args:
            text: 要截断的文本
            max_length: 最大长度

        Returns:
            str: 截断后的文本
        """
        if len(text) <= max_length:
            return text

        # 在句子边界截断
        sentence_endings = ['。', '！', '？', '.', '!', '?']

        # 从max_length向前查找句子结束符
        for i in range(max_length, max(0, max_length - 100), -1):
            if i < len(text) and text[i] in sentence_endings:
                return text[:i+1]

        # 如果找不到句子边界，在词边界截断
        for i in range(max_length, max(0, max_length - 50), -1):
            if i < len(text) and text[i] in [' ', '，', '、', '；']:
                return text[:i] + "..."

        # 最后直接截断
        return text[:max_length-3] + "..."

    def _build_telegram_message(
        self,
        message_text: str,
        media_items: List[MediaItem],
        send_strategy: str,
        caption: str
    ) -> TelegramMessage:
        """
        构建TelegramMessage对象

        Args:
            message_text: 消息文本
            media_items: 媒体项列表
            send_strategy: 发送策略
            caption: 简短caption

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
                    disable_web_page_preview=True,  # 媒体组模式禁用链接预览
                    caption=caption
                )
            elif send_strategy == "text_with_preview":
                # 文本+预览模式（不发送媒体组，启用链接预览）
                return TelegramMessage(
                    text=message_text,
                    media_group=[],  # 不使用媒体组
                    parse_mode="Markdown",
                    disable_web_page_preview=False,  # 启用链接预览
                    caption=caption
                )
            else:
                # 纯文本模式
                return TelegramMessage(
                    text=message_text,
                    media_group=[],
                    parse_mode="Markdown",
                    disable_web_page_preview=False,  # 启用链接预览作为补偿
                    caption=caption
                )

        except Exception as e:
            self.logger.error(f"构建TelegramMessage失败: {str(e)}", exc_info=True)
            # 返回基础消息
            return TelegramMessage(
                text=message_text,
                parse_mode="Markdown",
                disable_web_page_preview=False,
                caption=caption
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