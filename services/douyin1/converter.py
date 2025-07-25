"""
抖音消息转换器 (Douyin1)

将抖音视频数据转换为Telegram消息格式。
继承MessageConverter，实现抖音视频内容的格式化和媒体处理。

主要功能：
1. 将抖音视频数据转换为TelegramMessage格式
2. 格式化视频信息（标题、描述、统计数据等）
3. 处理视频和封面媒体项
4. 支持批量转换
5. 错误处理和降级策略

作者: Assistant
创建时间: 2024年
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

from services.common.message_converter import MessageConverter, ConverterType, ConversionError
from services.common.telegram_message import TelegramMessage, MediaItem, MediaType


class DouyinConverter(MessageConverter):
    """抖音消息转换器"""

    def __init__(self):
        """初始化转换器"""
        super().__init__(ConverterType.DOUYIN)
        self.logger = logging.getLogger("douyin1.converter")
        self.logger.info("抖音消息转换器初始化完成")

    def convert(self, source_data: Any, **kwargs) -> TelegramMessage:
        """
        转换抖音视频数据为消息格式

        Args:
            source_data: 抖音视频数据（来自fetcher的_extract_video_info方法）
            **kwargs: 额外参数

        Returns:
            TelegramMessage: 转换后的消息

        Raises:
            ConversionError: 转换失败时抛出
        """
        try:
            if not self.validate_source_data(source_data):
                raise ConversionError("无效的抖音视频数据", source_data, "douyin1")

            # 格式化文本内容
            text_content = self._format_video_text(source_data)

            # 创建消息对象
            message = TelegramMessage.create_text_message(
                text=text_content,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )

            # 添加视频媒体项
            video_item = self._extract_video_media(source_data)
            if video_item:
                message.add_media(video_item)

            self.logger.debug(f"成功转换抖音视频: {source_data.get('aweme_id', 'unknown')}")
            return message

        except Exception as e:
            error_msg = f"转换抖音视频数据失败: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise ConversionError(error_msg, source_data, "douyin1") from e

    def convert_batch(self, source_data_list: List[Any], **kwargs) -> List[TelegramMessage]:
        """
        批量转换抖音视频数据

        Args:
            source_data_list: 抖音视频数据列表
            **kwargs: 额外参数

        Returns:
            List[TelegramMessage]: 转换后的消息列表
        """
        messages = []
        for i, data in enumerate(source_data_list):
            try:
                message = self.convert(data, **kwargs)
                messages.append(message)
                self.logger.debug(f"批量转换进度: {i+1}/{len(source_data_list)}")
            except Exception as e:
                self.logger.error(f"批量转换第{i+1}个视频失败: {str(e)}", exc_info=True)
                # 尝试降级处理
                fallback_message = self.handle_conversion_error(e, data)
                if fallback_message:
                    messages.append(fallback_message)

        self.logger.info(f"批量转换完成: {len(messages)}/{len(source_data_list)} 个视频")
        return messages

    def _format_video_text(self, video_data: Dict[str, Any]) -> str:
        """
        格式化视频文本内容

        Args:
            video_data: 视频数据

        Returns:
            str: 格式化后的文本内容
        """
        try:
            # 基本信息
            aweme_id = video_data.get('aweme_id', 'unknown')
            desc = video_data.get('desc', '').strip()
            caption = video_data.get('caption', '').strip()
            create_time = video_data.get('create_time', 0)

            # 作者信息
            author = video_data.get('author', {})
            author_nickname = author.get('nickname', '').strip()

            # 统计信息
            statistics = video_data.get('statistics', {})
            share_count = statistics.get('share_count', 0)
            digg_count = statistics.get('digg_count', 0)
            comment_count = statistics.get('comment_count', 0)

            # 音乐信息
            music = video_data.get('music', {})
            music_title = music.get('title', '').strip()
            music_author = music.get('author', '').strip()

            # 构建消息文本
            caption_parts = []

            # 第一行：仅标题
            title = desc or caption or f"抖音视频 {aweme_id}"
            max_title_length = 80
            if len(title) > max_title_length:
                title = title[:max_title_length] + "..."

            safe_title = self._escape_markdown(title)
            caption_parts.append(f"`{safe_title}`")

            # 第二行：统计信息 + 作者（用 • 分隔）
            stats_parts = []
            if digg_count > 0:
                stats_parts.append(f"❤️ {self._format_count(digg_count)}")
            if comment_count > 0:
                stats_parts.append(f"💬 {self._format_count(comment_count)}")
            if share_count > 0:
                stats_parts.append(f"🔄 {self._format_count(share_count)}")

            # 添加作者信息到统计行
            if author_nickname:
                safe_nickname = self._escape_markdown(author_nickname)
                stats_parts.append(f"👤 {safe_nickname}")

            if stats_parts:
                stats_parts = [f"`{part}`" for part in stats_parts]
                caption_parts.append(" • ".join(stats_parts))

            # 第三行：音乐信息（如果有）
            if music_title:
                max_music_length = 35
                if len(music_title) > max_music_length:
                    music_title = music_title[:max_music_length] + "..."

                safe_music_title = self._escape_markdown(music_title)
                music_text = f"🎵 {safe_music_title}"

                # 添加音乐作者（如果与视频作者不同）
                if music_author and music_author != author_nickname:
                    safe_music_author = self._escape_markdown(music_author)
                    music_text += f"` - {safe_music_author}`"

                # 将音乐信息设置为斜体
                music_text = f"`{music_text}`"
                caption_parts.append(music_text)

            # 第四行：标签
            if author_nickname:
                clean_author = author_nickname.replace('@', '').replace('#', '').replace('_', '').replace(' ', '')
                caption_parts.append(f"#{clean_author}")

            # 最后一行：查看原视频链接 + 日期
            if aweme_id:
                douyin_link = f"https://www.douyin.com/video/{aweme_id}"
                last_line = f"[查看原视频]({douyin_link})"

                # 将日期拼接到最后一行
                if create_time > 0:
                    time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d')
                    last_line += f" • `{time_str}`"

                caption_parts.append(last_line)

            return "\n\n".join(caption_parts)

        except Exception as e:
            self.logger.error(f"格式化视频文本失败: {str(e)}", exc_info=True)
            # 降级处理
            return f"抖音视频 {video_data.get('aweme_id', 'unknown')}"

    def _extract_video_media(self, video_data: Dict[str, Any]) -> Optional[MediaItem]:
        """
        提取视频媒体项

        Args:
            video_data: 视频数据

        Returns:
            Optional[MediaItem]: 视频媒体项，如果无法提取则返回None
        """
        try:
            video_info = video_data.get('video', {})
            if not video_info:
                return None

            # 获取视频URL列表
            url_list = video_info.get('url_list', [])
            if not url_list:
                return None

            # 选择最后一个可用的URL
            video_url = url_list[-1]
            if not video_url:
                return None

            # 提取视频属性
            width = video_info.get('width', 0)
            height = video_info.get('height', 0)
            duration = video_data.get('duration', 0)
            file_size = video_info.get('data_size', 0)

            # 获取封面作为缩略图
            cover_info = video_data.get('cover', {})
            thumbnail_url = None
            if cover_info:
                cover_url_list = cover_info.get('url_list', [])
                if cover_url_list:
                    thumbnail_url = cover_url_list[0]

            # 转换时长（毫秒转秒）
            duration_seconds = duration // 1000 if duration > 0 else None

            # 创建视频媒体项
            return MediaItem.create_video(
                url=video_url,
                width=width if width > 0 else None,
                height=height if height > 0 else None,
                duration=duration_seconds,
                thumbnail_url=thumbnail_url
            )

        except Exception as e:
            self.logger.error(f"提取视频媒体失败: {str(e)}", exc_info=True)
            return None



    def validate_source_data(self, source_data: Any) -> bool:
        """
        验证抖音视频数据的有效性

        Args:
            source_data: 要验证的源数据

        Returns:
            bool: 数据是否有效
        """
        try:
            if not isinstance(source_data, dict):
                return False

            # 检查必要字段
            if not source_data.get('aweme_id'):
                return False

            return True

        except Exception as e:
            self.logger.error(f"验证源数据失败: {str(e)}", exc_info=True)
            return False

    def extract_media_items(self, source_data: Any) -> List[MediaItem]:
        """
        从源数据中提取媒体项

        Args:
            source_data: 源数据

        Returns:
            List[MediaItem]: 提取的媒体项列表
        """
        media_items = []

        # 提取视频媒体
        video_item = self._extract_video_media(source_data)
        if video_item:
            media_items.append(video_item)

        return media_items

    def get_source_display_name(self, source_url: str) -> str:
        """
        获取数据源显示名称

        Args:
            source_url: 数据源URL

        Returns:
            str: 显示名称
        """
        try:
            parsed = urlparse(source_url)
            domain = parsed.netloc
            return f"抖音: {domain}"
        except Exception:
            return f"抖音: {source_url}"

    def _escape_markdown(self, text: str) -> str:
        """
        转义Markdown特殊字符

        Args:
            text: 原始文本

        Returns:
            str: 转义后的文本
        """
        if not text:
            return ""

        # Markdown特殊字符
        special_chars = ['*', '_', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

        for char in special_chars:
            text = text.replace(char, f'\\{char}')

        return text

    def _format_duration(self, duration_ms: int) -> str:
        """
        格式化时长

        Args:
            duration_ms: 时长（毫秒）

        Returns:
            str: 格式化后的时长字符串
        """
        try:
            seconds = duration_ms // 1000
            minutes = seconds // 60
            seconds = seconds % 60

            if minutes > 0:
                return f"{minutes}分{seconds}秒"
            else:
                return f"{seconds}秒"
        except Exception:
            return "未知"

    def _format_count(self, count: int) -> str:
        """
        格式化数字

        Args:
            count: 数字

        Returns:
            str: 格式化后的数字字符串
        """
        try:
            if count >= 10000:
                return f"{count/10000:.1f}万"
            elif count >= 1000:
                return f"{count/1000:.1f}k"
            else:
                return str(count)
        except Exception:
            return "0"

    def handle_conversion_error(self, error: Exception, source_data: Any) -> Optional[TelegramMessage]:
        """
        处理转换错误的降级策略

        Args:
            error: 转换过程中的异常
            source_data: 导致错误的源数据

        Returns:
            Optional[TelegramMessage]: 降级处理后的消息，如果无法处理则返回None
        """
        try:
            self.logger.error(f"抖音视频转换失败，尝试降级处理: {str(error)}")

            # 尝试提取基本信息
            if isinstance(source_data, dict):
                aweme_id = source_data.get('aweme_id', 'unknown')
                desc = source_data.get('desc', '')
                author = source_data.get('author', {})
                author_nickname = author.get('nickname', '未知用户')

                # 创建简化的消息
                fallback_text = f"🎵 **抖音视频**\n\n"
                fallback_text += f"📱 **视频ID：** {aweme_id}\n"
                fallback_text += f"👤 **作者：** {author_nickname}\n"

                if desc:
                    desc_short = desc[:100] + "..." if len(desc) > 100 else desc
                    fallback_text += f"📝 **描述：** {desc_short}\n"

                fallback_text += f"\n⚠️ 部分内容解析失败"

                return TelegramMessage.create_text_message(
                    text=fallback_text,
                    parse_mode="Markdown"
                )

            # 如果连基本信息都无法提取，返回通用错误消息
            return TelegramMessage.create_text_message(
                text="🎵 **抖音视频**\n\n⚠️ 内容解析失败",
                parse_mode="Markdown"
            )

        except Exception as fallback_error:
            self.logger.error(f"降级处理也失败: {str(fallback_error)}", exc_info=True)
            return None


def create_douyin_converter() -> DouyinConverter:
    """
    创建抖音转换器实例

    Returns:
        DouyinConverter: 转换器实例
    """
    return DouyinConverter()


# 测试函数
def test_douyin_converter():
    """测试抖音转换器功能"""
    print("🧪 开始测试抖音转换器...")

    # 创建转换器
    converter = create_douyin_converter()

    # 模拟视频数据
    test_video_data = {
        "aweme_id": "7451100350070787343",
        "desc": "这是一个测试视频的描述内容",
        "caption": "测试标题",
        "create_time": 1703001600,  # 2023-12-20 00:00:00
        "duration": 15000,  # 15秒
        "author": {
            "uid": "test_uid",
            "nickname": "测试用户",
            "signature": "这是用户的个性签名"
        },
        "statistics": {
            "play_count": 12345,
            "digg_count": 567,
            "comment_count": 89,
            "share_count": 12
        },
        "video": {
            "url_list": ["https://example.com/video.mp4"],
            "width": 720,
            "height": 1280,
            "data_size": 1024000
        },
        "cover": {
            "url_list": ["https://example.com/cover.jpg"]
        },
        "music": {
            "title": "测试音乐",
            "author": "音乐作者"
        },
        "share_url": "https://v.douyin.com/test/"
    }

    try:
        # 测试单个转换
        message = converter.convert(test_video_data)
        print(f"✅ 单个转换成功")
        print(f"📝 消息文本长度: {len(message.text)}")
        print(f"🎬 媒体数量: {message.media_count}")
        print(f"📱 消息类型: {'媒体消息' if message.has_media else '纯文本消息'}")

        # 测试批量转换
        batch_data = [test_video_data, test_video_data]
        messages = converter.convert_batch(batch_data)
        print(f"✅ 批量转换成功: {len(messages)} 条消息")

        print("🎉 抖音转换器测试完成！")

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_douyin_converter()