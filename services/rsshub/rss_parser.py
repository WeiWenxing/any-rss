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
        解析RSS内容

        Args:
            rss_content: RSS XML内容
            rss_url: RSS源URL

        Returns:
            List[RSSEntry]: RSS条目列表
        """
        try:
            # 使用feedparser解析RSS
            feed = feedparser.parse(rss_content)

            if feed.bozo and feed.bozo_exception:
                self.logger.warning(f"RSS格式警告: {feed.bozo_exception}")

            # 获取源信息
            source_title = getattr(feed.feed, 'title', None)

            entries = []
            for entry_data in feed.entries:
                try:
                    entry = self._parse_single_entry(entry_data, rss_url, source_title)
                    if entry:
                        entries.append(entry)
                except Exception as e:
                    self.logger.warning(f"解析单个条目失败: {str(e)}")
                    continue

            self.logger.debug(f"成功解析 {len(entries)} 个RSS条目")
            return entries

        except Exception as e:
            self.logger.error(f"解析RSS内容失败: {str(e)}", exc_info=True)
            raise

    def _parse_single_entry(self, entry_data: Any, rss_url: str, source_title: Optional[str]) -> Optional[RSSEntry]:
        """
        解析单个RSS条目

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

            if not title or not link:
                self.logger.warning(f"条目缺少必要信息: title='{title}', link='{link}'")
                return None

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
        """提取条目描述"""
        # 尝试多个字段
        for field in ['description', 'summary', 'subtitle']:
            value = getattr(entry_data, field, None)
            if value:
                return self._clean_html(value).strip()
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
        """提取完整内容"""
        # 尝试content字段
        content_list = getattr(entry_data, 'content', [])
        if content_list:
            # 取第一个content
            content_item = content_list[0]
            if hasattr(content_item, 'value'):
                return self._clean_html(content_item.value).strip()

        # 尝试content_encoded字段（RSS扩展）
        content_encoded = getattr(entry_data, 'content_encoded', None)
        if content_encoded:
            return self._clean_html(content_encoded).strip()

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
            from bs4 import BeautifulSoup

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

                    # 转换为绝对URL
                    absolute_url = entry.get_absolute_url(video_url)

                    # 添加为视频附件
                    entry.add_enclosure(absolute_url, 'video/mp4')
                    self.logger.debug(f"从内容中添加视频附件: {absolute_url}")

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
                    'length': enclosure.length
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
                        length=enclosure_dict.get('length')
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