"""
抖音消息格式化器

负责将抖音内容格式化为Telegram消息
"""

import logging
from typing import Dict, Optional


class DouyinFormatter:
    """抖音消息格式化器"""
    
    def __init__(self):
        """初始化格式化器"""
        logging.info("抖音消息格式化器初始化完成")

    def format_content_message(self, content_info: Dict) -> str:
        """
        格式化抖音内容为文字消息
        
        Args:
            content_info: 内容信息字典
            
        Returns:
            str: 格式化后的消息文本
        """
        try:
            # 提取基本信息
            title = content_info.get("title", "无标题").strip()
            author = content_info.get("author", "").strip()
            nickname = content_info.get("nickname", "").strip()
            share_url = content_info.get("share_url", "").strip()
            content_type = content_info.get("type", "").strip()
            time_str = content_info.get("time", "").strip()
            
            # 统计信息
            play_count = content_info.get("play", 0)
            like_count = content_info.get("like", 0)
            comment_count = content_info.get("comment", 0)
            
            # 媒体信息
            media_type = content_info.get("media_type", "")
            size = content_info.get("size", "")
            
            # 构建消息
            message_parts = []
            
            # 标题和作者
            if nickname and author and nickname != author:
                message_parts.append(f"🎬 {title}")
                message_parts.append(f"👤 {nickname} (@{author})")
            elif nickname:
                message_parts.append(f"🎬 {title}")
                message_parts.append(f"👤 {nickname}")
            elif author:
                message_parts.append(f"🎬 {title}")
                message_parts.append(f"👤 @{author}")
            else:
                message_parts.append(f"🎬 {title}")
            
            # 发布时间
            if time_str:
                message_parts.append(f"📅 {time_str}")
            
            # 内容类型和媒体信息
            if content_type:
                type_info = f"📺 {content_type}"
                if media_type == "video" and size:
                    type_info += f" ({size})"
                message_parts.append(type_info)
            
            # 统计信息
            stats_parts = []
            if play_count > 0:
                stats_parts.append(f"▶️ {self._format_count(play_count)}")
            if like_count > 0:
                stats_parts.append(f"❤️ {self._format_count(like_count)}")
            if comment_count > 0:
                stats_parts.append(f"💬 {self._format_count(comment_count)}")
            
            if stats_parts:
                message_parts.append(" | ".join(stats_parts))
            
            # 分享链接
            if share_url:
                message_parts.append(f"🔗 {share_url}")
            
            # 音乐信息（如果有）
            music_info = content_info.get("music", {})
            if music_info and music_info.get("title"):
                music_title = music_info.get("title", "")
                music_author = music_info.get("author", "")
                music_duration = music_info.get("duration", "")
                
                music_text = f"🎵 {music_title}"
                if music_author and music_author != author:
                    music_text += f" - {music_author}"
                if music_duration:
                    music_text += f" ({music_duration})"
                
                message_parts.append(music_text)
            
            return "\n".join(message_parts)
            
        except Exception as e:
            logging.error(f"格式化抖音内容消息失败: {str(e)}", exc_info=True)
            return f"抖音内容: {content_info.get('title', '无标题')}"

    def format_caption(self, content_info: Dict) -> str:
        """
        格式化抖音内容为媒体caption（简洁版本）
        
        Args:
            content_info: 内容信息字典
            
        Returns:
            str: 格式化后的caption文本
        """
        try:
            # 提取基本信息
            title = content_info.get("title", "无标题").strip()
            author = content_info.get("author", "").strip()
            nickname = content_info.get("nickname", "").strip()
            
            # 构建简洁的caption
            caption_parts = []
            
            # 作者标签
            if author:
                caption_parts.append(f"#{author}")
            elif nickname:
                caption_parts.append(f"#{nickname}")
            
            # 标题（限制长度）
            max_title_length = 100
            if len(title) > max_title_length:
                title = title[:max_title_length] + "..."
            caption_parts.append(title)
            
            return " ".join(caption_parts)
            
        except Exception as e:
            logging.error(f"格式化抖音caption失败: {str(e)}", exc_info=True)
            return content_info.get("title", "抖音内容")

    def _format_count(self, count: int) -> str:
        """
        格式化数字（如播放量、点赞数等）
        
        Args:
            count: 数字
            
        Returns:
            str: 格式化后的数字字符串
        """
        if count >= 10000:
            return f"{count / 10000:.1f}万"
        elif count >= 1000:
            return f"{count / 1000:.1f}k"
        else:
            return str(count) 