"""
统一Telegram消息实体模块

定义跨模块的标准Telegram消息格式，确保所有数据源模块（douyin、rss、rsshub等）
都输出相同的消息结构，便于统一处理和发送。
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from enum import Enum


class MediaType(Enum):
    """媒体类型枚举"""
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


# ParseMode枚举已移除，直接使用字符串格式：
# "Markdown", "HTML", "MarkdownV2" 或 None


@dataclass
class MediaItem:
    """
    媒体项实体

    对应Telegram MediaGroup中的单个媒体项，包含媒体的所有必要信息
    """
    type: str                           # 媒体类型（photo/video/audio/document）
    url: str                           # 媒体URL
    caption: Optional[str] = None      # 媒体标题（通常只有第一个媒体项有caption）
    width: Optional[int] = None        # 媒体宽度（图片/视频）
    height: Optional[int] = None       # 媒体高度（图片/视频）
    duration: Optional[int] = None     # 媒体时长（视频/音频，单位：秒）
    file_size: Optional[int] = None    # 文件大小（字节）
    file_name: Optional[str] = None    # 文件名（文档类型）
    thumbnail_url: Optional[str] = None # 缩略图URL（视频）

    def __post_init__(self):
        """数据验证"""
        if not self.url:
            raise ValueError("MediaItem的url不能为空")

        # 验证媒体类型
        valid_types = [item.value for item in MediaType]
        if self.type not in valid_types:
            raise ValueError(f"无效的媒体类型: {self.type}，支持的类型: {valid_types}")

        # 验证数值类型
        for attr_name in ['width', 'height', 'duration', 'file_size']:
            value = getattr(self, attr_name)
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ValueError(f"{attr_name}必须是非负整数")

    @classmethod
    def create_photo(cls, url: str, caption: Optional[str] = None,
                    width: Optional[int] = None, height: Optional[int] = None) -> 'MediaItem':
        """创建图片媒体项的便捷方法"""
        return cls(
            type=MediaType.PHOTO.value,
            url=url,
            caption=caption,
            width=width,
            height=height
        )

    @classmethod
    def create_video(cls, url: str, caption: Optional[str] = None,
                    width: Optional[int] = None, height: Optional[int] = None,
                    duration: Optional[int] = None, thumbnail_url: Optional[str] = None) -> 'MediaItem':
        """创建视频媒体项的便捷方法"""
        return cls(
            type=MediaType.VIDEO.value,
            url=url,
            caption=caption,
            width=width,
            height=height,
            duration=duration,
            thumbnail_url=thumbnail_url
        )

    @classmethod
    def create_audio(cls, url: str, caption: Optional[str] = None,
                    duration: Optional[int] = None, file_name: Optional[str] = None) -> 'MediaItem':
        """创建音频媒体项的便捷方法"""
        return cls(
            type=MediaType.AUDIO.value,
            url=url,
            caption=caption,
            duration=duration,
            file_name=file_name
        )

    @classmethod
    def create_document(cls, url: str, caption: Optional[str] = None,
                       file_name: Optional[str] = None, file_size: Optional[int] = None) -> 'MediaItem':
        """创建文档媒体项的便捷方法"""
        return cls(
            type=MediaType.DOCUMENT.value,
            url=url,
            caption=caption,
            file_name=file_name,
            file_size=file_size
        )


@dataclass
class TelegramMessage:
    """
    统一Telegram消息实体

    所有模块（douyin、rss、rsshub等）的最终输出格式，确保消息结构的一致性
    """
    text: str                                    # 消息文本内容
    media_group: List[MediaItem] = field(default_factory=list)  # 媒体组列表
    parse_mode: Optional[str] = "Markdown"        # 解析模式
    disable_web_page_preview: bool = False       # 是否禁用链接预览
    reply_markup: Optional[Dict[str, Any]] = None # 可选的键盘标记

    def __post_init__(self):
        """数据验证"""
        if not self.text:
            raise ValueError("TelegramMessage的text不能为空")

        # 验证解析模式
        if self.parse_mode is not None:
            valid_modes = ["Markdown", "HTML", "MarkdownV2"]
            if self.parse_mode not in valid_modes:
                raise ValueError(f"无效的解析模式: {self.parse_mode}，支持的模式: {valid_modes}")

        # 验证媒体组
        if self.media_group:
            if len(self.media_group) > 10:
                raise ValueError("Telegram MediaGroup最多支持10个媒体项")

            # 检查caption分布（通常只有第一个媒体项有caption）
            caption_count = sum(1 for item in self.media_group if item.caption)
            if caption_count > 1:
                logging.warning("MediaGroup中有多个媒体项包含caption，Telegram可能只显示第一个")

    @property
    def has_media(self) -> bool:
        """是否包含媒体"""
        return len(self.media_group) > 0

    @property
    def media_count(self) -> int:
        """媒体数量"""
        return len(self.media_group)

    @property
    def is_media_group(self) -> bool:
        """是否为媒体组消息（包含2个或以上媒体）"""
        return len(self.media_group) >= 2

    @property
    def is_single_media(self) -> bool:
        """是否为单媒体消息（包含1个媒体）"""
        return len(self.media_group) == 1

    @property
    def is_text_only(self) -> bool:
        """是否为纯文本消息（不包含媒体）"""
        return len(self.media_group) == 0

    def add_media(self, media_item: MediaItem) -> None:
        """添加媒体项"""
        if len(self.media_group) >= 10:
            raise ValueError("MediaGroup已达到最大限制（10个媒体项）")
        self.media_group.append(media_item)

    def add_photo(self, url: str, caption: Optional[str] = None,
                  width: Optional[int] = None, height: Optional[int] = None) -> None:
        """添加图片媒体项的便捷方法"""
        self.add_media(MediaItem.create_photo(url, caption, width, height))

    def add_video(self, url: str, caption: Optional[str] = None,
                  width: Optional[int] = None, height: Optional[int] = None,
                  duration: Optional[int] = None, thumbnail_url: Optional[str] = None) -> None:
        """添加视频媒体项的便捷方法"""
        self.add_media(MediaItem.create_video(url, caption, width, height, duration, thumbnail_url))

    def clear_media(self) -> None:
        """清空所有媒体项"""
        self.media_group.clear()

    def get_media_by_type(self, media_type: str) -> List[MediaItem]:
        """根据类型获取媒体项"""
        return [item for item in self.media_group if item.type == media_type]

    def get_photos(self) -> List[MediaItem]:
        """获取所有图片媒体项"""
        return self.get_media_by_type(MediaType.PHOTO.value)

    def get_videos(self) -> List[MediaItem]:
        """获取所有视频媒体项"""
        return self.get_media_by_type(MediaType.VIDEO.value)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于序列化）"""
        return {
            'text': self.text,
            'media_group': [
                {
                    'type': item.type,
                    'url': item.url,
                    'caption': item.caption,
                    'width': item.width,
                    'height': item.height,
                    'duration': item.duration,
                    'file_size': item.file_size,
                    'file_name': item.file_name,
                    'thumbnail_url': item.thumbnail_url
                }
                for item in self.media_group
            ],
            'parse_mode': self.parse_mode,
            'disable_web_page_preview': self.disable_web_page_preview,
            'reply_markup': self.reply_markup
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TelegramMessage':
        """从字典创建实例（用于反序列化）"""
        media_group = []
        for item_data in data.get('media_group', []):
            media_item = MediaItem(
                type=item_data['type'],
                url=item_data['url'],
                caption=item_data.get('caption'),
                width=item_data.get('width'),
                height=item_data.get('height'),
                duration=item_data.get('duration'),
                file_size=item_data.get('file_size'),
                file_name=item_data.get('file_name'),
                thumbnail_url=item_data.get('thumbnail_url')
            )
            media_group.append(media_item)

        return cls(
            text=data['text'],
            media_group=media_group,
            parse_mode=data.get('parse_mode', "Markdown"),
            disable_web_page_preview=data.get('disable_web_page_preview', False),
            reply_markup=data.get('reply_markup')
        )

    @classmethod
    def create_text_message(cls, text: str, parse_mode: Optional[str] = None,
                           disable_web_page_preview: bool = False) -> 'TelegramMessage':
        """创建纯文本消息的便捷方法"""
        return cls(
            text=text,
            parse_mode=parse_mode or "Markdown",
            disable_web_page_preview=disable_web_page_preview
        )

    @classmethod
    def create_media_message(cls, text: str, media_items: List[MediaItem],
                            parse_mode: Optional[str] = None) -> 'TelegramMessage':
        """创建媒体消息的便捷方法"""
        return cls(
            text=text,
            media_group=media_items,
            parse_mode=parse_mode or "Markdown"
        )


def create_simple_text_message(text: str) -> TelegramMessage:
    """创建简单文本消息的快捷函数"""
    return TelegramMessage.create_text_message(text)


def create_single_photo_message(text: str, photo_url: str, caption: Optional[str] = None) -> TelegramMessage:
    """创建单图片消息的快捷函数"""
    message = TelegramMessage.create_text_message(text)
    message.add_photo(photo_url, caption)
    return message


def create_single_video_message(text: str, video_url: str, caption: Optional[str] = None,
                               duration: Optional[int] = None) -> TelegramMessage:
    """创建单视频消息的快捷函数"""
    message = TelegramMessage.create_text_message(text)
    message.add_video(video_url, caption, duration=duration)
    return message


# 导出主要类和函数
__all__ = [
    'TelegramMessage',
    'MediaItem',
    'MediaType',
    'create_simple_text_message',
    'create_single_photo_message',
    'create_single_video_message'
]