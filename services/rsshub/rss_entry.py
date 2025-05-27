"""
RSS条目实体模块

该模块定义RSS/Atom XML数据的标准化结构，作为RSSHub模块的核心数据实体。
支持RSS 2.0和Atom 1.0格式，提供统一的数据访问接口。

主要功能：
1. RSS条目的标准化数据结构
2. RSS/Atom格式的兼容性处理
3. 媒体附件的提取和管理
4. 条目唯一性标识生成
5. 数据验证和格式化

作者: Assistant
创建时间: 2024年
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse


@dataclass
class RSSEnclosure:
    """
    RSS媒体附件实体

    对应RSS <enclosure> 标签或Atom <link rel="enclosure"> 元素
    """
    url: str                    # 媒体文件URL
    type: str                   # MIME类型 (image/jpeg, video/mp4等)
    length: Optional[int] = None # 文件大小（字节）

    def __post_init__(self):
        """数据验证和标准化"""
        if not self.url:
            raise ValueError("媒体附件URL不能为空")

        # 标准化MIME类型
        if self.type:
            self.type = self.type.lower().strip()

        # 验证文件大小
        if self.length is not None and self.length < 0:
            self.length = None

    @property
    def is_image(self) -> bool:
        """判断是否为图片类型"""
        return self.type.startswith('image/') if self.type else False

    @property
    def is_video(self) -> bool:
        """判断是否为视频类型"""
        return self.type.startswith('video/') if self.type else False

    @property
    def is_audio(self) -> bool:
        """判断是否为音频类型"""
        return self.type.startswith('audio/') if self.type else False


@dataclass
class RSSEntry:
    """
    RSS条目实体

    统一的RSS/Atom条目数据结构，兼容RSS 2.0和Atom 1.0格式
    """
    # 基础信息
    title: str                          # 条目标题
    link: str                           # 条目链接
    description: str                    # 条目描述/摘要

    # 元数据
    guid: Optional[str] = None          # 全局唯一标识符
    published: Optional[datetime] = None # 发布时间
    updated: Optional[datetime] = None   # 更新时间
    author: Optional[str] = None        # 作者
    category: Optional[str] = None      # 分类

    # 内容信息
    content: Optional[str] = None       # 完整内容（Atom content或RSS content:encoded）
    summary: Optional[str] = None       # 摘要（Atom summary）

    # 媒体附件
    enclosures: List[RSSEnclosure] = field(default_factory=list)

    # 源信息
    source_url: str = ""                # RSS源URL
    source_title: Optional[str] = None  # RSS源标题

    # 内部字段
    raw_data: Dict[str, Any] = field(default_factory=dict)  # 原始解析数据
    _item_id: Optional[str] = None      # 缓存的条目ID

    def __post_init__(self):
        """数据验证和标准化处理"""
        self.logger = logging.getLogger(__name__)

        # 验证必填字段
        if not self.title:
            raise ValueError("RSS条目标题不能为空")
        if not self.link:
            raise ValueError("RSS条目链接不能为空")

        # 标准化字符串字段
        self.title = self.title.strip()
        self.link = self.link.strip()
        self.description = (self.description or "").strip()

        # 处理作者信息
        if self.author:
            self.author = self.author.strip()

        # 处理分类信息
        if self.category:
            self.category = self.category.strip()

        # 验证和标准化时间
        self._validate_timestamps()

        # 生成条目ID
        self._generate_item_id()

        self.logger.debug(f"RSS条目初始化完成: {self.item_id}")

    def _validate_timestamps(self):
        """验证和标准化时间戳"""
        # 如果没有发布时间但有更新时间，使用更新时间作为发布时间
        if not self.published and self.updated:
            self.published = self.updated

        # 如果没有更新时间但有发布时间，使用发布时间作为更新时间
        if not self.updated and self.published:
            self.updated = self.published

    def _generate_item_id(self):
        """
        生成条目唯一标识符

        优先级：guid > link+title的hash > link的hash
        """
        if self.guid:
            # 使用RSS提供的GUID
            self._item_id = self.guid
        else:
            # 生成基于内容的hash ID
            content_for_hash = f"{self.link}|{self.title}"
            if self.published:
                content_for_hash += f"|{self.published.isoformat()}"

            hash_obj = hashlib.md5(content_for_hash.encode('utf-8'))
            self._item_id = hash_obj.hexdigest()

        self.logger.debug(f"生成条目ID: {self._item_id}")

    @property
    def item_id(self) -> str:
        """获取条目唯一标识符"""
        if not self._item_id:
            self._generate_item_id()
        return self._item_id

    @property
    def effective_content(self) -> str:
        """
        获取有效内容

        优先级：content > description > summary
        """
        if self.content:
            return self.content
        elif self.description:
            return self.description
        elif self.summary:
            return self.summary
        else:
            return ""

    @property
    def effective_published_time(self) -> Optional[datetime]:
        """获取有效的发布时间"""
        return self.published or self.updated

    @property
    def has_media(self) -> bool:
        """判断是否包含媒体附件"""
        return len(self.enclosures) > 0

    @property
    def media_count(self) -> int:
        """获取媒体附件数量"""
        return len(self.enclosures)

    @property
    def image_enclosures(self) -> List[RSSEnclosure]:
        """获取所有图片附件"""
        return [enc for enc in self.enclosures if enc.is_image]

    @property
    def video_enclosures(self) -> List[RSSEnclosure]:
        """获取所有视频附件"""
        return [enc for enc in self.enclosures if enc.is_video]

    @property
    def audio_enclosures(self) -> List[RSSEnclosure]:
        """获取所有音频附件"""
        return [enc for enc in self.enclosures if enc.is_audio]

    def add_enclosure(self, url: str, mime_type: str, length: Optional[int] = None) -> None:
        """
        添加媒体附件

        Args:
            url: 媒体文件URL
            mime_type: MIME类型
            length: 文件大小（可选）
        """
        try:
            enclosure = RSSEnclosure(url=url, type=mime_type, length=length)
            self.enclosures.append(enclosure)
            self.logger.debug(f"添加媒体附件: {url} ({mime_type})")
        except Exception as e:
            self.logger.warning(f"添加媒体附件失败: {url}, 错误: {str(e)}")

    def get_absolute_url(self, relative_url: str) -> str:
        """
        将相对URL转换为绝对URL

        Args:
            relative_url: 相对URL

        Returns:
            str: 绝对URL
        """
        if not relative_url:
            return relative_url

        # 如果已经是绝对URL，直接返回
        if urlparse(relative_url).netloc:
            return relative_url

        # 使用条目链接作为基础URL
        base_url = self.link
        if not base_url:
            return relative_url

        try:
            return urljoin(base_url, relative_url)
        except Exception as e:
            self.logger.warning(f"URL转换失败: {relative_url}, 错误: {str(e)}")
            return relative_url

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        Returns:
            Dict[str, Any]: 条目的字典表示
        """
        return {
            'item_id': self.item_id,
            'title': self.title,
            'link': self.link,
            'description': self.description,
            'guid': self.guid,
            'published': self.published.isoformat() if self.published else None,
            'updated': self.updated.isoformat() if self.updated else None,
            'author': self.author,
            'category': self.category,
            'content': self.content,
            'summary': self.summary,
            'source_url': self.source_url,
            'source_title': self.source_title,
            'enclosures': [
                {
                    'url': enc.url,
                    'type': enc.type,
                    'length': enc.length
                }
                for enc in self.enclosures
            ],
            'media_count': self.media_count,
            'has_media': self.has_media
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RSSEntry':
        """
        从字典创建RSS条目实例

        Args:
            data: 条目数据字典

        Returns:
            RSSEntry: RSS条目实例
        """
        # 处理时间字段
        published = None
        if data.get('published'):
            try:
                published = datetime.fromisoformat(data['published'])
            except ValueError:
                pass

        updated = None
        if data.get('updated'):
            try:
                updated = datetime.fromisoformat(data['updated'])
            except ValueError:
                pass

        # 处理媒体附件
        enclosures = []
        for enc_data in data.get('enclosures', []):
            try:
                enclosure = RSSEnclosure(
                    url=enc_data['url'],
                    type=enc_data['type'],
                    length=enc_data.get('length')
                )
                enclosures.append(enclosure)
            except Exception:
                continue

        # 创建RSS条目实例
        entry = cls(
            title=data['title'],
            link=data['link'],
            description=data.get('description', ''),
            guid=data.get('guid'),
            published=published,
            updated=updated,
            author=data.get('author'),
            category=data.get('category'),
            content=data.get('content'),
            summary=data.get('summary'),
            source_url=data.get('source_url', ''),
            source_title=data.get('source_title'),
            enclosures=enclosures
        )

        return entry

    def __str__(self) -> str:
        """字符串表示"""
        return f"RSSEntry(id={self.item_id}, title='{self.title[:50]}...', media={self.media_count})"

    def __repr__(self) -> str:
        """详细字符串表示"""
        return (f"RSSEntry(item_id='{self.item_id}', title='{self.title}', "
                f"link='{self.link}', published={self.published}, "
                f"media_count={self.media_count})")


# 便捷函数：创建RSS条目实例
def create_rss_entry(
    title: str,
    link: str,
    description: str = "",
    **kwargs
) -> RSSEntry:
    """
    创建RSS条目实例的便捷函数

    Args:
        title: 条目标题
        link: 条目链接
        description: 条目描述
        **kwargs: 其他可选参数

    Returns:
        RSSEntry: RSS条目实例
    """
    return RSSEntry(
        title=title,
        link=link,
        description=description,
        **kwargs
    )


# 便捷函数：创建媒体附件
def create_enclosure(url: str, mime_type: str, length: Optional[int] = None) -> RSSEnclosure:
    """
    创建媒体附件的便捷函数

    Args:
        url: 媒体文件URL
        mime_type: MIME类型
        length: 文件大小（可选）

    Returns:
        RSSEnclosure: 媒体附件实例
    """
    return RSSEnclosure(url=url, type=mime_type, length=length)


if __name__ == "__main__":
    # 模块测试代码
    import json
    from datetime import datetime

    def test_rss_entry():
        """测试RSS条目实体功能"""
        print("🧪 RSS条目实体模块测试")

        # 测试创建基础RSS条目
        entry = create_rss_entry(
            title="测试RSS条目",
            link="https://example.com/article/1",
            description="这是一个测试RSS条目的描述",
            author="测试作者",
            published=datetime.now()
        )
        print(f"✅ 创建基础RSS条目: {entry.item_id}")

        # 测试添加媒体附件
        entry.add_enclosure(
            "https://example.com/image.jpg",
            "image/jpeg",
            1024000
        )
        entry.add_enclosure(
            "https://example.com/video.mp4",
            "video/mp4",
            5120000
        )
        print(f"✅ 添加媒体附件: {entry.media_count}个")

        # 测试媒体分类
        print(f"✅ 图片附件: {len(entry.image_enclosures)}个")
        print(f"✅ 视频附件: {len(entry.video_enclosures)}个")
        print(f"✅ 音频附件: {len(entry.audio_enclosures)}个")

        # 测试序列化
        entry_dict = entry.to_dict()
        print(f"✅ 序列化为字典: {len(entry_dict)}个字段")

        # 测试反序列化
        restored_entry = RSSEntry.from_dict(entry_dict)
        print(f"✅ 反序列化: {restored_entry.item_id}")

        # 测试条目比较
        print(f"✅ 条目ID一致: {entry.item_id == restored_entry.item_id}")

        # 测试字符串表示
        print(f"✅ 字符串表示: {str(entry)}")

        print("🎉 RSS条目实体模块测试完成")

    # 运行测试
