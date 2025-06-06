"""
RSS解析器模块

该模块负责从RSS/Atom XML解析出标准化的RSSEntry对象。
支持RSS 2.0和Atom 1.0格式，提供统一的解析接口。

主要功能：
1. RSS/Atom XML的解析和处理
2. 媒体附件的提取和处理
3. 内容清理和格式化
4. 错误处理和容错机制
5. 编码检测和处理

作者: Assistant
创建时间: 2024年
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from urllib.parse import urljoin, urlparse
import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import hashlib
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime

from .rss_entry import RSSEntry, RSSEnclosure, create_rss_entry
from services.common.cache import get_cache


class RSSParser:
    """
    RSS解析器

    负责从RSS/Atom XML解析出标准化的RSSEntry对象列表
    """

    def __init__(self, timeout: int = 30, max_retries: int = 3, cache_ttl: int = 21600):
        """
        初始化RSS解析器

        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            cache_ttl: 缓存过期时间（秒），默认6小时
        """
        self.logger = logging.getLogger(__name__)
        self.timeout = timeout
        self.max_retries = max_retries

        # 初始化缓存
        self.cache = get_cache("rsshub_parser", ttl=cache_ttl)

        # 配置HTTP会话
        self.session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 设置完善的请求头（与普通RSS模块保持一致）
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache'
        })

        self.logger.info(f"RSS解析器初始化完成，超时: {timeout}s, 重试: {max_retries}次, 缓存TTL: {cache_ttl}s")

    def _generate_cache_key(self, rss_url: str) -> str:
        """
        生成缓存键

        Args:
            rss_url: RSS源URL

        Returns:
            str: 缓存键
        """
        # 使用URL生成唯一的缓存键
        cache_key = hashlib.md5(rss_url.encode('utf-8')).hexdigest()
        return f"rss_feed:{cache_key}"

    def parse_feed(self, rss_url: str) -> List[RSSEntry]:
        """
        解析RSS源，返回RSS条目列表（带缓存）

        Args:
            rss_url: RSS源URL

        Returns:
            List[RSSEntry]: RSS条目列表

        Raises:
            Exception: 解析失败时抛出异常
        """
        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(rss_url)

            # 尝试从缓存获取数据
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                self.logger.info(f"📦 从缓存获取RSS内容: {rss_url}, 条目数: {len(cached_data)}")
                # 将缓存的字典数据转换回RSSEntry对象
                entries = []
                for entry_dict in cached_data:
                    try:
                        entry = self._dict_to_rss_entry(entry_dict)
                        if entry:
                            entries.append(entry)
                    except Exception as e:
                        self.logger.warning(f"缓存条目转换失败: {str(e)}")
                        continue
                return entries

            self.logger.info(f"🌐 开始解析RSS源: {rss_url}")

            # 获取RSS内容
            rss_content = self._fetch_rss_content(rss_url)

            # 解析RSS内容
            entries = self._parse_rss_content(rss_content, rss_url)

            # 缓存解析结果（转换为字典格式）
            if entries:
                cache_data = []
                for entry in entries:
                    try:
                        entry_dict = self._rss_entry_to_dict(entry)
                        cache_data.append(entry_dict)
                    except Exception as e:
                        self.logger.warning(f"条目序列化失败: {str(e)}")
                        continue

                self.cache.set(cache_key, cache_data)
                self.logger.info(f"💾 RSS内容已缓存: {rss_url}, 条目数: {len(cache_data)}")

            self.logger.info(f"RSS解析完成: {rss_url}, 获取到 {len(entries)} 个条目")
            return entries

        except Exception as e:
            error_msg = f"RSS解析失败: {rss_url}, 错误: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            raise Exception(error_msg)

    def _fetch_rss_content(self, rss_url: str) -> str:
        """
        获取RSS内容

        Args:
            rss_url: RSS源URL

        Returns:
            str: RSS XML内容
        """
        try:
            self.logger.debug(f"获取RSS内容: {rss_url}")

            response = self.session.get(rss_url, timeout=self.timeout)
            response.raise_for_status()

            # 检测编码
            content = response.content
            encoding = response.encoding or 'utf-8'

            # 尝试解码
            try:
                rss_content = content.decode(encoding)
            except UnicodeDecodeError:
                # 如果解码失败，尝试其他编码
                for fallback_encoding in ['utf-8', 'gbk', 'gb2312', 'latin1']:
                    try:
                        rss_content = content.decode(fallback_encoding)
                        self.logger.debug(f"使用备用编码 {fallback_encoding} 解码成功")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # 所有编码都失败，使用错误处理
                    rss_content = content.decode('utf-8', errors='ignore')
                    self.logger.warning(f"编码检测失败，使用UTF-8忽略错误模式")

            self.logger.debug(f"RSS内容获取成功: {len(rss_content)} 字符")
            return rss_content

        except Exception as e:
            self.logger.error(f"获取RSS内容失败: {rss_url}, 错误: {str(e)}", exc_info=True)
            raise

    def _parse_rss_content(self, rss_content: str, rss_url: str) -> List[RSSEntry]:
        """
        解析RSS内容，优先使用BeautifulSoup，失败则回退到feedparser

        Args:
            rss_content: RSS XML内容
            rss_url: RSS源URL

        Returns:
            List[RSSEntry]: RSS条目列表
        """
        try:
            self.logger.info(f"🚀 尝试使用主解析器(BeautifulSoup)解析RSS内容, URL: {rss_url}")
            return self._parse_rss_content_with_soup(rss_content, rss_url)
        except Exception as e:
            self.logger.error(f"主解析器(BeautifulSoup)解析失败: {e}", exc_info=True)
            self.logger.warning(f"正在尝试回退到备用解析器(feedparser)...")
            try:
                return self._parse_rss_content_with_feedparser(rss_content, rss_url)
            except Exception as fp_e:
                self.logger.error(f"备用解析器(feedparser)也失败了: {fp_e}", exc_info=True)
                raise fp_e

    def _parse_rss_content_with_soup(self, rss_content: str, rss_url: str) -> List[RSSEntry]:
        """
        使用BeautifulSoup解析RSS内容

        Args:
            rss_content: RSS XML内容
            rss_url: RSS源URL

        Returns:
            List[RSSEntry]: RSS条目列表
        """
        soup = BeautifulSoup(rss_content, 'xml')

        # 获取源信息
        source_title = soup.find('channel').find('title').get_text(strip=True) if soup.find('channel') and soup.find('channel').find('title') else '未知来源'

        entries = []
        # feedparser有时会把item放在entries里，bs4是直接找item
        items = soup.find_all('item')
        if not items:
            self.logger.warning(f"在 {rss_url} 中未找到<item>标签，尝试在'entries'中查找")
            items = soup.find_all('entry')

        if not items:
            self.logger.error(f"在 {rss_url} 中未找到任何<item>或<entry>标签")
            return []

        self.logger.info(f"🔍 在 {rss_url} 中找到 {len(items)} 个条目")

        for item_soup in items:
            try:
                entry = self._parse_single_entry_with_soup(item_soup, rss_url, source_title)
                if entry:
                    entries.append(entry)
            except Exception as e:
                self.logger.warning(f"使用BeautifulSoup解析单个条目失败: {e}", exc_info=True)
                continue

        self.logger.info(f"✅ 使用BeautifulSoup成功解析 {len(entries)} 个RSS条目")
        return entries

    def _parse_single_entry_with_soup(self, item_soup: BeautifulSoup, rss_url: str, source_title: Optional[str]) -> Optional[RSSEntry]:
        """
        使用BeautifulSoup解析单个RSS条目

        Args:
            item_soup: 单个<item>的BeautifulSoup对象
            rss_url: RSS源URL
            source_title: RSS源标题

        Returns:
            Optional[RSSEntry]: RSS条目对象，解析失败返回None
        """
        # 提取各个字段
        title = item_soup.find('title').get_text(strip=True) if item_soup.find('title') else ""
        link = item_soup.find('link').get_text(strip=True) if item_soup.find('link') else ""

        # 1. 正确提取完整的HTML内容，而不是纯文本
        description = self._extract_description_with_soup(item_soup)
        author = self._extract_author_with_soup(item_soup)
        category = self._extract_category_with_soup(item_soup)
        content = self._extract_content_with_soup(item_soup)
        summary = self._extract_summary_with_soup(item_soup)

        pub_date_tag = item_soup.find('pubDate')
        pub_date_str = pub_date_tag.get_text(strip=True) if pub_date_tag else None

        published_time = None
        if pub_date_str:
            parsed_date = feedparser.parse(f'<rss><channel><item><pubDate>{pub_date_str}</pubDate></item></channel></rss>')
            if parsed_date.entries and 'published_parsed' in parsed_date.entries[0]:
                published_time = self._parse_datetime(parsed_date.entries[0].published_parsed)

        updated_tag = item_soup.find('updated')
        updated_str = updated_tag.get_text(strip=True) if updated_tag else None
        updated_time = None
        if updated_str:
            parsed_date = feedparser.parse(f'<rss><channel><item><updated>{updated_str}</updated></item></channel></rss>')
            if parsed_date.entries and 'updated_parsed' in parsed_date.entries[0]:
                updated_time = self._parse_datetime(parsed_date.entries[0].updated_parsed)

        guid = self._extract_guid_with_soup(item_soup, link)

        raw_data = {'soup_str': str(item_soup)}

        # 2. 创建RSSEntry对象，此时传入的是原始HTML
        entry = create_rss_entry(
            guid=guid,
            title=title,
            link=link,
            description=description,
            author=author,
            category=category,
            published=published_time,
            updated=updated_time,
            content=content,
            summary=summary,
            raw_data=raw_data,
            source_url=rss_url,
            source_title=source_title
        )

        # 3. 提取媒体附件（此过程会清理HTML）
        # 3a. 优先解析标准的enclosure标签
        for enclosure in item_soup.find_all('enclosure'):
            url = enclosure.get('url')
            mime_type = enclosure.get('type')
            length_str = enclosure.get('length')
            if url and mime_type:
                length = int(length_str) if length_str and length_str.isdigit() else 0
                entry.add_enclosure(url=url, mime_type=mime_type, length=length)

        # 3b. 然后从description中提取媒体内容作为补充
        self._extract_media_from_content_with_soup(item_soup, entry)

        # 4. 最后，对清理后的HTML进行Markdown转换
        entry.description = self._html_to_markdown(entry.description)
        entry.content = self._html_to_markdown(entry.content)
        entry.summary = entry.description

        return entry

    def _extract_content_with_soup(self, item_soup: BeautifulSoup) -> str:
        """使用BeautifulSoup提取完整内容的HTML"""
        # 尝试多个字段，返回第一个找到的完整HTML内容
        for field in ['content', 'content:encoded']:
            tag = item_soup.find(field)
            if tag:
                return tag.decode_contents(formatter="html")
        return ""

    def _extract_summary_with_soup(self, item_soup: BeautifulSoup) -> str:
        """使用BeautifulSoup提取摘要的HTML"""
        tag = item_soup.find('summary')
        if tag:
            return tag.decode_contents(formatter="html")
        return ""

    def _extract_category_with_soup(self, item_soup: BeautifulSoup) -> Optional[str]:
        """使用BeautifulSoup提取分类信息"""
        # 优先查找category标签
        category_tag = item_soup.find('category')
        if category_tag:
            # 优先使用term属性
            term = category_tag.get('term')
            if term:
                return term.strip()
            # 否则使用标签文本
            text = category_tag.get_text(strip=True)
            if text:
                return text
        return None

    def _extract_author_with_soup(self, item_soup: BeautifulSoup) -> Optional[str]:
        """使用BeautifulSoup提取作者信息"""
        # 尝试 author -> name 结构
        author_tag = item_soup.find('author')
        if author_tag and author_tag.find('name'):
            name_text = author_tag.find('name').get_text(strip=True)
            if name_text:
                return name_text

        # 如果没有 name 子标签，直接尝试 author 标签的文本
        if author_tag:
            author_text = author_tag.get_text(strip=True)
            if author_text:
                return author_text

        # 尝试 dc:creator 标签
        creator_tag = item_soup.find('dc:creator')
        if creator_tag:
            creator_text = creator_tag.get_text(strip=True)
            if creator_text:
                return creator_text

        return None

    def _extract_guid_with_soup(self, item_soup: BeautifulSoup, link: str) -> str:
        """使用BeautifulSoup提取GUID，优先使用id，然后是guid，最后回退到link"""
        # 尝试多个字段，返回第一个找到的
        for field in ['id', 'guid']:
            tag = item_soup.find(field)
            if tag and tag.get_text(strip=True):
                return tag.get_text(strip=True)
        # 如果都没有，回退到link
        return link

    def _extract_description_with_soup(self, item_soup: BeautifulSoup) -> str:
        """使用BeautifulSoup提取条目描述的完整HTML内容并转换为Markdown格式"""
        # 尝试多个字段，返回第一个找到的完整HTML内容
        for field in ['description', 'summary', 'subtitle']:
            tag = item_soup.find(field)
            if tag:
                html_content = tag.decode_contents(formatter="html")
                return self._html_to_markdown(html_content).strip()
        return ""

    def _extract_media_from_content_with_soup(self, description_soup: BeautifulSoup, entry: RSSEntry):
        """从BeautifulSoup解析的description中提取媒体附件，并从HTML中移除它们"""
        if not description_soup:
            return

        # 提取图片
        img_tags = description_soup.find_all('img')
        if img_tags:
            self.logger.debug(f"在 {entry.item_id} 中找到 {len(img_tags)} 个<img>标签")
            for img in img_tags:
                img_url = img.get('src')
                if img_url:
                    # 将相对URL转换为绝对URL
                    full_img_url = urljoin(entry.link or entry.rss_url, img_url)
                    enclosure = RSSEnclosure(url=full_img_url, type='image', length=0)
                    if enclosure not in entry.enclosures:
                        entry.enclosures.append(enclosure)

            # 从description中移除已经提取的img标签
            for img in img_tags:
                img.decompose()

            # 更新入口的description和content为清理后的HTML
            cleaned_html = description_soup.decode_contents(formatter="html")
            entry.description = cleaned_html
            if entry.content == entry.summary: # 如果content和description相同，一起更新
                entry.content = cleaned_html
            entry.summary = cleaned_html

    def _parse_rss_content_with_feedparser(self, rss_content: str, rss_url: str) -> List[RSSEntry]:
        """
        (备用) 使用feedparser解析RSS内容
        """
        try:
            # 使用feedparser解析RSS
            feed = feedparser.parse(rss_content)

            if feed.bozo and feed.bozo_exception:
                self.logger.warning(f"Feedparser RSS格式警告: {feed.bozo_exception}")

            # 获取源信息
            source_title = getattr(feed.feed, 'title', None)

            entries = []
            for entry_data in feed.entries:
                try:
                    entry = self._parse_single_entry(entry_data, rss_url, source_title)
                    if entry:
                        entries.append(entry)
                except Exception as e:
                    self.logger.warning(f"Feedparser解析单个条目失败: {str(e)}")
                    continue

            self.logger.debug(f"Feedparser成功解析 {len(entries)} 个RSS条目")
            return entries

        except Exception as e:
            self.logger.error(f"Feedparser解析RSS内容失败: {str(e)}", exc_info=True)
            raise

    def _parse_single_entry(self, entry_data: Any, rss_url: str, source_title: Optional[str]) -> Optional[RSSEntry]:
        """
        (备用) 解析单个RSS条目

        Args:
            entry_data: feedparser解析的条目数据
            rss_url: RSS源URL
            source_title: RSS源标题

        Returns:
            Optional[RSSEntry]: RSS条目对象，解析失败返回None
        """
        try:
            # 提取基础信息
            title = getattr(entry_data, 'title', '').strip()
            link = getattr(entry_data, 'link', '').strip()

            # 允许标题和链接都为空，不进行验证和自动生成
            self.logger.debug(f"解析条目: title='{title}', link='{link}'")

            # 提取描述
            description = self._extract_description(entry_data)

            # 提取GUID
            guid = getattr(entry_data, 'id', None) or getattr(entry_data, 'guid', None)

            # 提取时间
            published = self._parse_datetime(getattr(entry_data, 'published_parsed', None))
            updated = self._parse_datetime(getattr(entry_data, 'updated_parsed', None))

            # 提取作者
            author = self._extract_author(entry_data)

            # 提取分类
            category = self._extract_category(entry_data)

            # 提取内容
            content = self._extract_content(entry_data)
            summary = getattr(entry_data, 'summary', None)

            # 创建RSS条目
            entry = create_rss_entry(
                title=title,
                link=link,
                description=description,
                guid=guid,
                published=published,
                updated=updated,
                author=author,
                category=category,
                content=content,
                summary=summary,
                source_url=rss_url,
                source_title=source_title,
                raw_data=entry_data
            )

            # 提取媒体附件
            self._extract_enclosures(entry_data, entry)

            # 从内容中提取额外的媒体
            self._extract_media_from_content(entry)

            return entry

        except Exception as e:
            self.logger.error(f"解析单个条目失败: {str(e)}", exc_info=True)
            return None

    def _extract_description(self, entry_data: Any) -> str:
        """提取条目描述，转换为Markdown格式"""
        # 尝试多个字段
        for field in ['description', 'summary', 'subtitle']:
            value = getattr(entry_data, field, None)
            if value:
                return self._html_to_markdown(value).strip()
        return ""

    def _extract_author(self, entry_data: Any) -> Optional[str]:
        """提取作者信息"""
        # 尝试多个字段
        author = getattr(entry_data, 'author', None)
        if author:
            return author.strip()

        # 尝试author_detail
        author_detail = getattr(entry_data, 'author_detail', None)
        if author_detail and hasattr(author_detail, 'name'):
            return author_detail.name.strip()

        return None

    def _extract_category(self, entry_data: Any) -> Optional[str]:
        """提取分类信息"""
        tags = getattr(entry_data, 'tags', [])
        if tags:
            # 取第一个标签作为分类
            first_tag = tags[0]
            if hasattr(first_tag, 'term'):
                return first_tag.term.strip()
            elif isinstance(first_tag, str):
                return first_tag.strip()

        return None

    def _extract_content(self, entry_data: Any) -> Optional[str]:
        """提取完整内容，转换为Markdown格式"""
        # 尝试content字段
        content_list = getattr(entry_data, 'content', [])
        if content_list:
            # 取第一个content
            content_item = content_list[0]
            if hasattr(content_item, 'value'):
                return self._html_to_markdown(content_item.value).strip()

        # 尝试content_encoded字段（RSS扩展）
        content_encoded = getattr(entry_data, 'content_encoded', None)
        if content_encoded:
            return self._html_to_markdown(content_encoded).strip()

        return None

    def _extract_enclosures(self, entry_data: Any, entry: RSSEntry) -> None:
        """提取媒体附件"""
        # 处理enclosures字段
        enclosures = getattr(entry_data, 'enclosures', [])
        for enclosure in enclosures:
            try:
                url = getattr(enclosure, 'href', '') or getattr(enclosure, 'url', '')
                mime_type = getattr(enclosure, 'type', '')
                length = getattr(enclosure, 'length', None)

                if url and mime_type:
                    # 转换长度为整数
                    if length:
                        try:
                            length = int(length)
                        except (ValueError, TypeError):
                            length = None

                    entry.add_enclosure(url, mime_type, length)

            except Exception as e:
                self.logger.warning(f"处理enclosure失败: {str(e)}")
                continue

    def _extract_media_from_content(self, entry: RSSEntry) -> None:
        """从内容中提取媒体链接（参考普通RSS模块的策略）"""
        # 获取原始HTML内容（未清理的）
        raw_content = None

        # 尝试从原始数据中获取HTML内容
        if hasattr(entry, 'raw_data') and entry.raw_data:
            # 尝试content字段
            content_list = getattr(entry.raw_data, 'content', [])
            if content_list:
                content_item = content_list[0]
                if hasattr(content_item, 'value'):
                    raw_content = content_item.value

            # 如果没有content，尝试content_encoded
            if not raw_content:
                raw_content = getattr(entry.raw_data, 'content_encoded', None)

            # 如果还没有，尝试description/summary
            if not raw_content:
                raw_content = getattr(entry.raw_data, 'description', None) or getattr(entry.raw_data, 'summary', None)

        # 如果没有原始数据，使用已有的有效内容（虽然可能已被清理）
        if not raw_content:
            raw_content = entry.effective_content

        if not raw_content:
            return

        self.logger.debug(f"从内容中提取媒体，原始内容长度: {len(raw_content)} 字符")

        # 使用BeautifulSoup解析HTML（参考普通RSS模块的策略）
        try:
            # 解析HTML内容
            soup = BeautifulSoup(raw_content, 'html.parser')

            # 提取图片
            img_tags = soup.find_all('img', src=True)
            self.logger.debug(f"使用BeautifulSoup找到 {len(img_tags)} 个img标签")

            for img_tag in img_tags:
                try:
                    img_url = img_tag.get('src', '').strip()
                    if not img_url or not img_url.startswith(('http://', 'https://')):
                        continue

                    # 过滤装饰图片（参考普通RSS模块的策略）
                    if any(keyword in img_url.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'button']):
                        self.logger.debug(f"过滤装饰图片: {img_url}")
                        continue

                    # 转换为绝对URL
                    absolute_url = entry.get_absolute_url(img_url)

                    # 添加为图片附件
                    entry.add_enclosure(absolute_url, 'image/jpeg')
                    self.logger.debug(f"从内容中添加图片附件: {absolute_url}")

                except Exception as e:
                    self.logger.debug(f"处理内容图片失败: {img_url}, 错误: {str(e)}")
                    continue

            # 提取视频（参考普通RSS模块的策略）
            video_tags = soup.find_all('video', src=True)
            self.logger.debug(f"使用BeautifulSoup找到 {len(video_tags)} 个video标签")

            for video_tag in video_tags:
                try:
                    video_url = video_tag.get('src', '').strip()
                    if not video_url or not video_url.startswith(('http://', 'https://')):
                        continue

                    # 提取poster封面图URL
                    poster_url = video_tag.get('poster', '').strip()
                    if poster_url and not poster_url.startswith(('http://', 'https://')):
                        # 转换相对URL为绝对URL
                        poster_url = entry.get_absolute_url(poster_url)

                    # 转换视频URL为绝对URL
                    absolute_url = entry.get_absolute_url(video_url)

                    # 添加为视频附件，包含poster信息
                    entry.add_enclosure(absolute_url, 'video/mp4', poster=poster_url if poster_url else None)

                    poster_info = f" (封面: {poster_url})" if poster_url else ""
                    self.logger.debug(f"从内容中添加视频附件: {absolute_url}{poster_info}")

                except Exception as e:
                    self.logger.debug(f"处理内容视频失败: {video_url}, 错误: {str(e)}")
                    continue

        except ImportError:
            self.logger.warning("BeautifulSoup不可用，回退到正则表达式解析")
            # 回退到原来的正则表达式方法
            img_pattern = r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>'
            img_matches = re.findall(img_pattern, raw_content, re.IGNORECASE)

            self.logger.debug(f"正则表达式找到 {len(img_matches)} 个img标签")

            for img_url in img_matches:
                try:
                    # 过滤装饰图片
                    if any(keyword in img_url.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'button']):
                        self.logger.debug(f"过滤装饰图片: {img_url}")
                        continue

                    # 转换为绝对URL
                    absolute_url = entry.get_absolute_url(img_url)

                    # 添加为图片附件
                    entry.add_enclosure(absolute_url, 'image/jpeg')
                    self.logger.debug(f"从内容中添加图片附件: {absolute_url}")

                except Exception as e:
                    self.logger.debug(f"处理内容图片失败: {img_url}, 错误: {str(e)}")
                    continue

        except Exception as e:
            self.logger.warning(f"媒体提取失败: {str(e)}")
            return

    def _parse_datetime(self, time_struct) -> Optional[datetime]:
        """解析时间结构"""
        if not time_struct:
            return None

        try:
            return datetime(*time_struct[:6])
        except (TypeError, ValueError):
            return None

    def _clean_html(self, html_content: str) -> str:
        """清理HTML标签"""
        if not html_content:
            return ""

        # 简单的HTML标签清理
        clean_text = re.sub(r'<[^>]+>', '', html_content)

        # 清理多余的空白字符
        clean_text = re.sub(r'\s+', ' ', clean_text)

        return clean_text.strip()

    def _html_to_markdown(self, html_content: str) -> str:
        """
        将HTML内容转换为Telegram Markdown格式

        Args:
            html_content: HTML内容

        Returns:
            str: Telegram Markdown格式的内容
        """
        if not html_content:
            return ""

        self.logger.debug(f"HTML转Markdown - 原始内容长度: {len(html_content)}")

        try:
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # 统计原始HTML标签
            original_tags = {
                'h标签': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
                'p标签': len(soup.find_all('p')),
                'div标签': len(soup.find_all('div')),
                'strong/b标签': len(soup.find_all(['strong', 'b'])),
                'em/i标签': len(soup.find_all(['em', 'i'])),
                'a标签': len(soup.find_all('a')),
                'li标签': len(soup.find_all('li')),
                'br标签': len(soup.find_all('br'))
            }
            self.logger.debug(f"原始HTML标签统计: {original_tags}")

            # 1. 处理标题 - Telegram不支持#语法，转为粗体
            for h_tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                h_text = h_tag.get_text().strip()
                if h_text:
                    # 创建新的标签结构：换行 + 斜体 + 换行
                    new_content = soup.new_string(f"\n\n*{h_text}*\n\n")
                    h_tag.replace_with(new_content)
                    self.logger.debug(f"转换标题: {h_tag.name} -> *{h_text}*")
                else:
                    h_tag.decompose()

            # 2. 处理段落 - 添加段落分隔
            for p_tag in soup.find_all('p'):
                p_text = p_tag.get_text().strip()
                if p_text:
                    # 保留段落内的其他格式化标签，只替换p标签本身
                    p_tag.name = 'div'  # 临时改名，避免重复处理
                    new_content = soup.new_string(f"\n\n{p_text}\n\n")
                    p_tag.replace_with(new_content)
                    self.logger.debug(f"转换段落: {len(p_text)}字符")
                else:
                    p_tag.decompose()

            # 3. 处理div - 添加段落分隔
            for div_tag in soup.find_all('div'):
                div_text = div_tag.get_text().strip()
                if div_text:
                    new_content = soup.new_string(f"\n\n{div_text}\n\n")
                    div_tag.replace_with(new_content)
                    self.logger.debug(f"转换div: {len(div_text)}字符")
                else:
                    div_tag.decompose()

            # 4. 处理换行标签
            for br_tag in soup.find_all('br'):
                br_tag.replace_with(soup.new_string('\n'))
                self.logger.debug("转换br标签为换行")

            # 5. 处理粗体标签
            strong_count = 0
            for strong_tag in soup.find_all(['strong', 'b']):
                strong_text = strong_tag.get_text().strip()
                if strong_text:
                    new_content = soup.new_string(f"**{strong_text}**")
                    strong_tag.replace_with(new_content)
                    strong_count += 1
                    self.logger.debug(f"转换粗体: {strong_text}")
                else:
                    strong_tag.decompose()

            # 6. 处理斜体标签
            em_count = 0
            for em_tag in soup.find_all(['em', 'i']):
                em_text = em_tag.get_text().strip()
                if em_text:
                    new_content = soup.new_string(f"*{em_text}*")
                    em_tag.replace_with(new_content)
                    em_count += 1
                    self.logger.debug(f"转换斜体: {em_text}")
                else:
                    em_tag.decompose()

            # 7. 处理链接标签
            link_count = 0
            for a_tag in soup.find_all('a', href=True):
                link_text = a_tag.get_text().strip()
                link_href = a_tag.get('href', '').strip()

                if link_text and link_href:
                    # Telegram链接格式: [文本](URL)
                    new_content = soup.new_string(f"[{link_text}]({link_href})")
                    a_tag.replace_with(new_content)
                    link_count += 1
                    self.logger.debug(f"转换链接: {link_text} -> {link_href}")
                else:
                    # 如果没有文本或链接，保留文本部分
                    if link_text:
                        a_tag.replace_with(soup.new_string(link_text))
                    else:
                        a_tag.decompose()

            # 8. 处理列表项
            li_count = 0
            for li_tag in soup.find_all('li'):
                li_text = li_tag.get_text().strip()
                if li_text:
                    # Telegram不支持特殊列表语法，使用普通的项目符号
                    new_content = soup.new_string(f"\n• {li_text}")
                    li_tag.replace_with(new_content)
                    li_count += 1
                    self.logger.debug(f"转换列表项: {li_text}")
                else:
                    li_tag.decompose()

            # 9. 清理剩余的HTML标签（保留文本内容）
            remaining_tags = soup.find_all()
            remaining_count = len(remaining_tags)
            if remaining_count > 0:
                self.logger.debug(f"清理剩余HTML标签: {remaining_count}个")
                for tag in remaining_tags:
                    tag_text = tag.get_text()
                    if tag_text.strip():
                        tag.replace_with(soup.new_string(tag_text))
                    else:
                        tag.decompose()

            # 10. 获取最终文本
            final_text = soup.get_text()

            # 11. 清理空白字符，保留段落结构
            # 处理HTML实体
            final_text = final_text.replace('&nbsp;', ' ')
            final_text = final_text.replace('&amp;', '&')
            final_text = final_text.replace('&lt;', '<')
            final_text = final_text.replace('&gt;', '>')
            final_text = final_text.replace('&quot;', '"')
            final_text = final_text.replace('&#39;', "'")
            final_text = final_text.replace('&hellip;', '...')
            final_text = final_text.replace('&mdash;', '—')
            final_text = final_text.replace('&ndash;', '–')

            # 清理多余的空白字符
            final_text = re.sub(r'[ \t]+', ' ', final_text)  # 行内多余空格
            final_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', final_text)  # 多空行合并为双空行
            final_text = final_text.strip()  # 去掉首尾空白

            # 12. 最终清理段落空格
            lines = final_text.split('\n')
            cleaned_lines = []
            for line in lines:
                cleaned_line = line.strip()
                # 保留空行用于段落分隔，但避免连续多个空行
                if cleaned_line or (not cleaned_lines or cleaned_lines[-1]):
                    cleaned_lines.append(cleaned_line)

            final_text = '\n'.join(cleaned_lines)
            final_text = re.sub(r'\n\n+', '\n\n', final_text)  # 最终确保不超过双空行

            # 13. 统计转换结果
            markdown_stats = {
                '粗体': len(re.findall(r'\*\*[^*]+\*\*', final_text)),
                '斜体': len(re.findall(r'\*[^*]+\*', final_text)),
                '链接': len(re.findall(r'\[[^\]]+\]\([^)]+\)', final_text)),
                '列表项': len(re.findall(r'\n• ', final_text))
            }

            self.logger.debug(f"HTML转Markdown完成 - 最终长度: {len(final_text)}")
            self.logger.debug(f"Telegram Markdown元素统计: {markdown_stats}")

            return final_text

        except ImportError:
            self.logger.warning("BeautifulSoup不可用，回退到简单HTML清理")
            # 回退到简单的HTML标签清理
            clean_text = re.sub(r'<[^>]+>', '', html_content)
            clean_text = re.sub(r'\s+', ' ', clean_text)
            return clean_text.strip()

        except Exception as e:
            self.logger.error(f"HTML转Markdown失败: {str(e)}", exc_info=True)
            # 出错时回退到简单清理
            clean_text = re.sub(r'<[^>]+>', '', html_content)
            clean_text = re.sub(r'\s+', ' ', clean_text)
            return clean_text.strip()

    def validate_rss_url(self, rss_url: str) -> bool:
        """
        验证RSS URL是否有效（宽松验证，与普通RSS模块保持一致）

        Args:
            rss_url: RSS源URL

        Returns:
            bool: 是否有效
        """
        try:
            # 基础URL格式验证
            parsed = urlparse(rss_url)
            if not parsed.scheme or not parsed.netloc:
                self.logger.debug(f"RSS URL格式验证失败: 缺少协议或域名 - {rss_url}")
                return False

            # 检查协议
            if parsed.scheme not in ['http', 'https']:
                self.logger.debug(f"RSS URL协议验证失败: 不支持的协议 {parsed.scheme} - {rss_url}")
                return False

            # 宽松验证：尝试直接解析RSS内容（不依赖Content-Type）
            try:
                self.logger.debug(f"开始宽松验证RSS源: {rss_url}")
                entries = self.parse_feed(rss_url)
                self.logger.debug(f"RSS源验证成功: 解析到 {len(entries)} 个条目 - {rss_url}")
                return True  # 能解析就认为有效
            except Exception as parse_error:
                self.logger.debug(f"RSS内容解析失败: {rss_url}, 错误: {str(parse_error)}")

                # 如果解析失败，尝试简单的连通性检查
                try:
                    self.logger.debug(f"尝试连通性检查: {rss_url}")
                    response = self.session.head(rss_url, timeout=10)
                    response.raise_for_status()
                    self.logger.debug(f"连通性检查通过，假设RSS源有效: {rss_url}")
                    return True  # 连通性正常，假设RSS源有效
                except Exception as conn_error:
                    self.logger.debug(f"连通性检查也失败: {rss_url}, 错误: {str(conn_error)}")
                    return False

        except Exception as e:
            self.logger.debug(f"RSS URL验证失败: {rss_url}, 错误: {str(e)}")
            return False

    def get_feed_info(self, rss_url: str) -> Dict[str, Any]:
        """
        获取RSS源信息

        Args:
            rss_url: RSS源URL

        Returns:
            Dict[str, Any]: RSS源信息
        """
        try:
            rss_content = self._fetch_rss_content(rss_url)
            feed = feedparser.parse(rss_content)

            return {
                'title': getattr(feed.feed, 'title', ''),
                'description': getattr(feed.feed, 'description', ''),
                'link': getattr(feed.feed, 'link', ''),
                'language': getattr(feed.feed, 'language', ''),
                'updated': self._parse_datetime(getattr(feed.feed, 'updated_parsed', None)),
                'entry_count': len(feed.entries),
                'version': feed.version
            }

        except Exception as e:
            self.logger.error(f"获取RSS源信息失败: {rss_url}, 错误: {str(e)}", exc_info=True)
            return {}

    def _rss_entry_to_dict(self, entry: RSSEntry) -> Dict[str, Any]:
        """
        将RSSEntry对象转换为字典格式（用于缓存）

        Args:
            entry: RSSEntry对象

        Returns:
            Dict[str, Any]: 字典格式的条目数据
        """
        try:
            entry_dict = {
                'title': entry.title,
                'link': entry.link,
                'description': entry.description,
                'guid': entry.guid,
                'published': entry.published.isoformat() if entry.published else None,
                'updated': entry.updated.isoformat() if entry.updated else None,
                'author': entry.author,
                'category': entry.category,
                'content': entry.content,
                'summary': entry.summary,
                'source_url': entry.source_url,
                'source_title': entry.source_title,
                'enclosures': []
            }

            # 序列化附件
            for enclosure in entry.enclosures:
                enclosure_dict = {
                    'url': enclosure.url,
                    'mime_type': enclosure.type,
                    'length': enclosure.length,
                    'poster': enclosure.poster
                }
                entry_dict['enclosures'].append(enclosure_dict)

            return entry_dict

        except Exception as e:
            self.logger.error(f"RSSEntry序列化失败: {str(e)}", exc_info=True)
            raise

    def _dict_to_rss_entry(self, entry_dict: Dict[str, Any]) -> Optional[RSSEntry]:
        """
        将字典格式转换为RSSEntry对象（从缓存恢复）

        Args:
            entry_dict: 字典格式的条目数据

        Returns:
            Optional[RSSEntry]: RSSEntry对象
        """
        try:
            # 解析时间
            published = None
            if entry_dict.get('published'):
                try:
                    published = datetime.fromisoformat(entry_dict['published'])
                except ValueError:
                    pass

            updated = None
            if entry_dict.get('updated'):
                try:
                    updated = datetime.fromisoformat(entry_dict['updated'])
                except ValueError:
                    pass

            # 创建RSSEntry对象
            entry = create_rss_entry(
                title=entry_dict.get('title', ''),
                link=entry_dict.get('link', ''),
                description=entry_dict.get('description', ''),
                guid=entry_dict.get('guid'),
                published=published,
                updated=updated,
                author=entry_dict.get('author'),
                category=entry_dict.get('category'),
                content=entry_dict.get('content'),
                summary=entry_dict.get('summary'),
                source_url=entry_dict.get('source_url'),
                source_title=entry_dict.get('source_title')
            )

            # 恢复附件
            for enclosure_dict in entry_dict.get('enclosures', []):
                try:
                    entry.add_enclosure(
                        url=enclosure_dict.get('url', ''),
                        mime_type=enclosure_dict.get('mime_type', ''),
                        length=enclosure_dict.get('length'),
                        poster=enclosure_dict.get('poster')
                    )
                except Exception as e:
                    self.logger.warning(f"恢复附件失败: {str(e)}")
                    continue

            return entry

        except Exception as e:
            self.logger.error(f"字典转RSSEntry失败: {str(e)}", exc_info=True)
            return None

    def clear_cache(self, rss_url: str = None) -> bool:
        """
        清除缓存

        Args:
            rss_url: 指定URL的缓存，如果为None则清除所有缓存

        Returns:
            bool: 是否成功
        """
        try:
            if rss_url:
                # 清除指定URL的缓存
                cache_key = self._generate_cache_key(rss_url)
                success = self.cache.delete(cache_key)
                self.logger.info(f"清除指定URL缓存: {rss_url}, 成功: {success}")
                return success
            else:
                # 清除所有缓存
                success = self.cache.clear()
                self.logger.info(f"清除所有RSS解析器缓存, 成功: {success}")
                return success
        except Exception as e:
            self.logger.error(f"清除缓存失败: {str(e)}", exc_info=True)
            return False

    def get_cache_info(self) -> Dict:
        """
        获取缓存信息

        Returns:
            Dict: 缓存统计信息
        """
        try:
            return self.cache.get_info()
        except Exception as e:
            self.logger.error(f"获取缓存信息失败: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def is_cache_hit(self, rss_url: str) -> bool:
        """
        检查指定URL是否有缓存

        Args:
            rss_url: RSS源URL

        Returns:
            bool: 是否有缓存
        """
        try:
            cache_key = self._generate_cache_key(rss_url)
            return self.cache.exists(cache_key)
        except Exception as e:
            self.logger.error(f"检查缓存失败: {str(e)}", exc_info=True)
            return False


# 便捷函数：创建RSS解析器实例
def create_rss_parser(timeout: int = 30, max_retries: int = 3, cache_ttl: int = 21600) -> RSSParser:
    """
    创建RSS解析器实例

    Args:
        timeout: 请求超时时间
        max_retries: 最大重试次数
        cache_ttl: 缓存过期时间（秒），默认6小时

    Returns:
        RSSParser: RSS解析器实例
    """
    return RSSParser(timeout, max_retries, cache_ttl)


# 便捷函数：快速解析RSS
def parse_rss_feed(rss_url: str, timeout: int = 30) -> List[RSSEntry]:
    """
    快速解析RSS源的便捷函数

    Args:
        rss_url: RSS源URL
        timeout: 请求超时时间

    Returns:
        List[RSSEntry]: RSS条目列表
    """
    parser = create_rss_parser(timeout=timeout)
    return parser.parse_feed(rss_url)


if __name__ == "__main__":
    # 模块测试代码
    def test_rss_parser():
        """测试RSS解析器功能"""
        print("🧪 RSS解析器模块测试")

        # 创建解析器
        parser = create_rss_parser()
        print(f"✅ 创建RSS解析器: {type(parser).__name__}")

        # 测试URL验证
        test_urls = [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://invalid-url",
            "not-a-url"
        ]

        for url in test_urls:
            is_valid = parser.validate_rss_url(url)
            print(f"✅ URL验证 {url}: {'有效' if is_valid else '无效'}")

        print("🎉 RSS解析器模块测试完成")

    # 运行测试
    test_rss_parser()