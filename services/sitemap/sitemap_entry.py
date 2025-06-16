"""
Sitemap条目定义模块

定义Sitemap条目的数据结构，只包含URL和最后修改时间。
支持XML和TXT格式的Sitemap解析。

注意：消息ID(message_id)由UnifiedContentManager统一管理，不在此类中定义。

作者: Assistant
创建时间: 2024年
"""

import logging
from typing import Optional, Any
from datetime import datetime
from dataclasses import dataclass


@dataclass
class SitemapEntry:
    """
    Sitemap条目

    表示Sitemap中的一个URL条目，只包含URL和最后修改时间。
    消息ID由UnifiedContentManager统一管理，用于跟踪已发送的消息。
    """

    url: str
    """URL地址"""
    
    last_modified: Optional[datetime] = None
    """最后修改时间"""

    def __post_init__(self):
        """初始化后的处理"""
        # 验证URL
        if not self.url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL: {self.url}")

    def to_dict(self) -> dict:
        """
        转换为字典

        Returns:
            dict: 字典表示
        """
        return {
            'url': self.url,
            'last_modified': self.last_modified.isoformat() if self.last_modified else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SitemapEntry':
        """
        从字典创建实例

        Args:
            data: 字典数据

        Returns:
            SitemapEntry: 实例
        """
        # 处理最后修改时间
        last_modified = None
        if data.get('last_modified'):
            try:
                last_modified = datetime.fromisoformat(data['last_modified'])
            except ValueError as e:
                logging.error(f"解析最后修改时间失败: {str(e)}", exc_info=True)
                
        return cls(
            url=data['url'],
            last_modified=last_modified
        )

    def __str__(self) -> str:
        """字符串表示"""
        parts = [f"URL: {self.url}"]
        if self.last_modified:
            parts.append(f"Last Modified: {self.last_modified}")
        return "\n".join(parts)

    def __eq__(self, other: Any) -> bool:
        """相等比较"""
        if not isinstance(other, SitemapEntry):
            return False
        return self.url == other.url

    def __hash__(self) -> int:
        """哈希值"""
        return hash(self.url) 