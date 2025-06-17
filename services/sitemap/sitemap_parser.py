"""
Sitemap解析器模块

提供Sitemap解析功能，支持XML和TXT格式，以及压缩格式。
支持解析Sitemap索引文件。

作者: Assistant
创建时间: 2024年
"""

import logging
import gzip
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
import requests
from urllib.parse import urlparse
import hashlib
import lxml.etree as etree
from dotenv import load_dotenv

from .sitemap_entry import SitemapEntry
from services.common.cache import get_cache

logger = logging.getLogger(__name__)

class SitemapParser:
    """Sitemap解析器"""

    def __init__(self, timeout: int = 30, max_retries: int = 3, cache_ttl: int = 21600):
        """
        初始化解析器

        Args:
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            cache_ttl: 缓存过期时间（秒），默认6小时
        """
        self.timeout = timeout
        self.max_retries = max_retries

        # 初始化缓存
        self.cache = get_cache("sitemap_parser", ttl=cache_ttl)

        logger.info(f"Sitemap解析器初始化完成，超时: {timeout}s, 重试: {max_retries}次, 缓存TTL: {cache_ttl}s")

    def _generate_cache_key(self, url: str) -> str:
        """
        生成缓存键

        Args:
            url: Sitemap URL

        Returns:
            str: 缓存键
        """
        # 使用URL生成唯一的缓存键
        cache_key = hashlib.md5(url.encode('utf-8')).hexdigest()
        return f"sitemap_feed:{cache_key}"

    def parse(self, url: str) -> List[SitemapEntry]:
        """
        解析Sitemap

        Args:
            url: Sitemap URL

        Returns:
            List[SitemapEntry]: 解析结果列表

        Raises:
            requests.RequestException: 网络请求错误
            etree.ParseError: XML解析错误
        """
        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(url)

            # 尝试从缓存获取数据
            cached_content = self.cache.get(cache_key)
            if cached_content is not None:
                logger.info(f"📦 从缓存获取Sitemap内容: {url}")
                content = cached_content
            else:
                logger.info(f"🌐 开始解析Sitemap: {url}")

                # 获取内容（同步requests实现）
                response = requests.get(url, timeout=self.timeout)
                response.raise_for_status()
                content = response.content

                # 缓存原始内容
                self.cache.set(cache_key, content)
                logger.info(f"💾 Sitemap内容已缓存: {url}")

            # 检查是否是gzip压缩
            is_gzip = False
            if url.endswith('.gz'):
                is_gzip = True
            elif isinstance(content, bytes) and content.startswith(b'\x1f\x8b'):  # gzip 魔数
                is_gzip = True

            if is_gzip:
                try:
                    content = gzip.decompress(content)
                except Exception as e:
                    logger.warning(f"gzip解压失败，尝试使用原始内容: {str(e)}")

            content = content.decode('utf-8')

            # 根据URL后缀判断格式
            if url.endswith('.txt'):
                entries = self._parse_txt(content)
            else:
                entries = self._parse_xml(content, url)

            # 限制数量
            entries = entries[:10]
            logger.info(f"📦 限制处理最近的{len(entries)}个条目")

            return entries

        except Exception as e:
            logger.error(f"解析Sitemap失败: {url}, 错误: {str(e)}", exc_info=True)
            raise

    def _parse_txt(self, content: str) -> List[SitemapEntry]:
        """
        解析TXT格式

        Args:
            content: 文件内容

        Returns:
            List[SitemapEntry]: 解析结果列表
        """
        entries = []
        for line in content.splitlines():
            line = line.strip()
            if line and line.startswith(('http://', 'https://')):
                entries.append(SitemapEntry(url=line))
        return entries

    def _parse_xml(self, content: str, base_url: str) -> List[SitemapEntry]:
        """
        解析XML格式

        Args:
            content: XML内容
            base_url: 基础URL，用于解析相对路径

        Returns:
            List[SitemapEntry]: 解析结果列表

        Raises:
            etree.ParseError: XML解析错误
        """
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            root = etree.fromstring(content.encode('utf-8'), parser=parser)

            # 检查是否是sitemap索引
            if root.tag.endswith('sitemapindex'):
                return self._parse_sitemap_index(root, base_url)

            # 解析普通sitemap
            entries = []
            logger.info("开始解析普通sitemap")

            # 获取所有命名空间
            namespaces = {
                'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9',
                'xhtml': 'http://www.w3.org/1999/xhtml',
                'image': 'http://www.google.com/schemas/sitemap-image/1.1',
                'video': 'http://www.google.com/schemas/sitemap-video/1.1',
                'news': 'http://www.google.com/schemas/sitemap-news/0.9'
            }
            logger.debug(f"使用的命名空间: {namespaces}")

            # 使用XPath查找所有URL元素
            url_elements = root.xpath('.//ns:url', namespaces=namespaces)
            logger.info(f"找到 {len(url_elements)} 个URL元素")

            # 统计信息
            total_urls = len(url_elements)
            valid_urls = 0
            invalid_urls = 0
            time_parse_errors = 0

            for i, url in enumerate(url_elements, 1):
                try:
                    logger.debug(f"处理第 {i}/{total_urls} 个URL元素")

                    # 获取URL
                    loc = url.find('ns:loc', namespaces=namespaces)
                    if loc is None or not loc.text:
                        logger.warning(f"URL元素 {i} 缺少loc标签或内容为空")
                        invalid_urls += 1
                        continue

                    url_text = loc.text.strip()
                    logger.debug(f"URL {i}: {url_text}")

                    # 获取最后修改时间
                    last_modified = None
                    lastmod = url.find('ns:lastmod', namespaces=namespaces)
                    if lastmod is not None and lastmod.text:
                        try:
                            # 处理ISO 8601格式的时间
                            time_str = lastmod.text.strip()
                            logger.debug(f"原始时间字符串: {time_str}")

                            if time_str.endswith('Z'):
                                time_str = time_str[:-1] + '+00:00'
                                logger.debug(f"转换后的时间字符串: {time_str}")

                            last_modified = datetime.fromisoformat(time_str)
                            logger.debug(f"解析时间成功: {time_str} -> {last_modified}")
                        except ValueError as e:
                            logger.warning(f"解析时间失败: {lastmod.text}, 错误: {str(e)}", exc_info=True)
                            time_parse_errors += 1
                    else:
                        logger.debug(f"URL {i} 没有最后修改时间")

                    # 创建SitemapEntry
                    entry = SitemapEntry(
                        url=url_text,
                        last_modified=last_modified
                    )
                    entries.append(entry)
                    valid_urls += 1

                except Exception as e:
                    logger.warning(f"处理URL元素 {i} 失败: {str(e)}", exc_info=True)
                    invalid_urls += 1
                    continue

            # 记录统计信息
            logger.info(f"解析完成 - 总数: {total_urls}, 有效: {valid_urls}, 无效: {invalid_urls}, 时间解析错误: {time_parse_errors}")

            return entries

        except Exception as e:
            logger.error(f"解析XML失败: {str(e)}", exc_info=True)
            raise

    def _parse_sitemap_index(self, root: etree._Element, base_url: str) -> List[SitemapEntry]:
        """
        解析Sitemap索引

        Args:
            root: XML根元素
            base_url: 基础URL

        Returns:
            List[SitemapEntry]: 解析结果列表
        """
        try:
            all_entries = []
            namespaces = {
                'ns': root.nsmap.get(None, 'http://www.sitemaps.org/schemas/sitemap/0.9')
            }

            # 获取所有sitemap URL
            sitemap_elements = root.xpath('.//ns:sitemap', namespaces=namespaces)
            logger.info(f"找到 {len(sitemap_elements)} 个sitemap索引")

            for sitemap in sitemap_elements:
                try:
                    # 获取sitemap URL
                    loc = sitemap.find('ns:loc', namespaces=namespaces)
                    if loc is None or not loc.text:
                        continue

                    url = loc.text.strip()
                    logger.info(f"处理sitemap: {url}")

                    try:
                        # 递归解析每个sitemap
                        entries = self.parse(url)
                        all_entries.extend(entries)
                    except Exception as e:
                        logger.warning(f"解析sitemap失败: {url}, 错误: {str(e)}", exc_info=True)
                        continue

                except Exception as e:
                    logger.warning(f"处理sitemap元素失败: {str(e)}", exc_info=True)
                    continue

            return all_entries

        except Exception as e:
            logger.error(f"解析sitemap索引失败: {str(e)}", exc_info=True)
            raise

    def clear_cache(self, url: str = None) -> bool:
        """
        清除缓存

        Args:
            url: 要清除的URL缓存，如果为None则清除所有缓存

        Returns:
            bool: 是否成功
        """
        try:
            if url:
                cache_key = self._generate_cache_key(url)
                self.cache.delete(cache_key)
                logger.info(f"清除缓存成功: {url}")
            else:
                self.cache.clear()
                logger.info("清除所有缓存成功")
            return True
        except Exception as e:
            logger.error(f"清除缓存失败: {str(e)}", exc_info=True)
            return False

    def get_cache_info(self) -> Dict:
        """
        获取缓存信息

        Returns:
            Dict: 缓存信息
        """
        try:
            return {
                'size': self.cache.size(),
                'ttl': self.cache.ttl,
                'hits': self.cache.hits,
                'misses': self.cache.misses
            }
        except Exception as e:
            logger.error(f"获取缓存信息失败: {str(e)}", exc_info=True)
            return {}

    def is_cache_hit(self, url: str) -> bool:
        """
        检查URL是否命中缓存

        Args:
            url: 要检查的URL

        Returns:
            bool: 是否命中缓存
        """
        try:
            cache_key = self._generate_cache_key(url)
            return self.cache.exists(cache_key)
        except Exception as e:
            logger.error(f"检查缓存命中失败: {str(e)}", exc_info=True)
            return False

def create_sitemap_parser(timeout: int = 30, max_retries: int = 3, cache_ttl: int = 21600) -> SitemapParser:
    """
    创建Sitemap解析器实例

    Args:
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
        cache_ttl: 缓存过期时间（秒）

    Returns:
        SitemapParser: 解析器实例
    """
    return SitemapParser(timeout=timeout, max_retries=max_retries, cache_ttl=cache_ttl)

if __name__ == '__main__':
    import sys
    import json
    from datetime import datetime

    # 加载环境变量
    load_dotenv()

    # 配置日志
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(funcName)s:%(lineno)d] - %(message)s',
        level=logging.INFO
    )

    def datetime_handler(x):
        if isinstance(x, datetime):
            return x.isoformat()
        raise TypeError(f"Object of type {type(x)} is not JSON serializable")

    if len(sys.argv) != 2:
        logger.error("Usage: python sitemap_parser.py <sitemap_url>")
        logger.error("Example: python sitemap_parser.py https://example.com/sitemap.xml")
        sys.exit(1)

    url = sys.argv[1]
    logger.info(f"正在解析Sitemap: {url}")

    parser = create_sitemap_parser()
    entries = parser.parse(url)

    logger.info(f"\n返回 {len(entries)} 个条目 (已限制为最近的10个):")
    for i, entry in enumerate(entries, 1):
        logger.info(f"\n条目 {i}:")
        logger.info(f"URL: {entry.url}")
        if entry.last_modified:
            logger.info(f"最后修改时间: {entry.last_modified.isoformat()}")

    # 输出JSON格式的完整结果
    logger.info("\n完整JSON结果:")
    logger.info(json.dumps([{
        'url': entry.url,
        'last_modified': entry.last_modified.isoformat() if entry.last_modified else None
    } for entry in entries], indent=2, ensure_ascii=False, default=datetime_handler))