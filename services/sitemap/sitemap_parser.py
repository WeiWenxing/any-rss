"""
Sitemap解析器模块

提供Sitemap解析功能，支持XML和TXT格式，以及压缩格式。
支持解析Sitemap索引文件。

作者: Assistant
创建时间: 2024年
"""

import logging
import gzip
import xml.etree.ElementTree as ET
from typing import List, Optional, Union, Dict, Any
from datetime import datetime
import requests
from urllib.parse import urlparse
import hashlib
import lxml.etree as etree

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
        self.session: Optional[requests.Session] = None
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
            ValueError: URL格式错误
            requests.RequestException: 网络请求错误
            ET.ParseError: XML解析错误
        """
        # 验证URL
        if not url.startswith(('http://', 'https://')):
            raise ValueError(f"Invalid URL: {url}")

        try:
            # 生成缓存键
            cache_key = self._generate_cache_key(url)

            # 尝试从缓存获取数据
            cached_data = self.cache.get(cache_key)
            if cached_data is not None:
                logger.info(f"📦 从缓存获取Sitemap内容: {url}, 条目数: {len(cached_data)}")
                # 将缓存的字典数据转换回SitemapEntry对象
                entries = []
                for entry_dict in cached_data:
                    try:
                        entry = self._dict_to_sitemap_entry(entry_dict)
                        if entry:
                            entries.append(entry)
                    except Exception as e:
                        logger.warning(f"缓存条目转换失败: {str(e)}")
                        continue
                return entries

            logger.info(f"🌐 开始解析Sitemap: {url}")

            # 获取内容（同步requests实现）
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            content = response.content

            # 检查是否是gzip压缩
            is_gzip = False
            if url.endswith('.gz'):
                is_gzip = True
            elif response.headers.get('content-encoding') == 'gzip':
                is_gzip = True
            elif content.startswith(b'\x1f\x8b'):  # gzip 魔数
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

            # 缓存解析结果（转换为字典格式）
            if entries:
                cache_data = []
                for entry in entries:
                    try:
                        entry_dict = self._sitemap_entry_to_dict(entry)
                        cache_data.append(entry_dict)
                    except Exception as e:
                        logger.warning(f"条目序列化失败: {str(e)}")
                        continue

                self.cache.set(cache_key, cache_data)
                logger.info(f"💾 Sitemap内容已缓存: {url}, 条目数: {len(cache_data)}")

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
            ET.ParseError: XML解析错误
        """
        try:
            root = ET.fromstring(content)

            # 检查是否是sitemap索引
            if root.tag.endswith('sitemapindex'):
                return self._parse_sitemap_index(root, base_url)

            # 解析普通sitemap
            entries = []
            logger.info("开始解析普通sitemap")

            # 获取所有命名空间
            namespaces = {
                'ns': root.nsmap.get(None, 'http://www.sitemaps.org/schemas/sitemap/0.9'),
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
                    logger.debug(f"✅ 添加URL成功: {entry.url}, 最后修改: {entry.last_modified}")

                except Exception as e:
                    logger.error(f"❌ 处理URL元素 {i} 失败: {str(e)}", exc_info=True)
                    invalid_urls += 1
                    continue

            # 输出统计信息
            logger.info(f"Sitemap解析完成:")
            logger.info(f"• 总URL数: {total_urls}")
            logger.info(f"• 有效URL数: {valid_urls}")
            logger.info(f"• 无效URL数: {invalid_urls}")
            logger.info(f"• 时间解析错误: {time_parse_errors}")

            if valid_urls == 0:
                logger.warning("⚠️ 未找到任何有效的URL")
            elif valid_urls < total_urls:
                logger.warning(f"⚠️ 部分URL解析失败: {invalid_urls}/{total_urls}")

            return entries

        except ET.ParseError as e:
            logger.error(f"解析XML失败: {str(e)}", exc_info=True)
            raise

    def _parse_sitemap_index(self, root: ET.Element, base_url: str) -> List[SitemapEntry]:
        """
        解析Sitemap索引

        Args:
            root: XML根元素
            base_url: 基础URL

        Returns:
            List[SitemapEntry]: 所有sitemap的条目列表
        """
        all_entries = []

        # 获取所有sitemap URL
        for sitemap in root.findall('.//{*}sitemap'):
            loc = sitemap.find('{*}loc')
            if loc is not None and loc.text:
                # 处理相对URL
                url = loc.text
                if not urlparse(url).netloc:
                    url = urlparse(base_url)._replace(path=url).geturl()

                try:
                    # 递归解析每个sitemap
                    entries = self.parse(url)
                    all_entries.extend(entries)
                except Exception as e:
                    logger.error(f"解析子sitemap失败: {url}", exc_info=True)

        return all_entries

    def _sitemap_entry_to_dict(self, entry: SitemapEntry) -> Dict[str, Any]:
        """
        将SitemapEntry对象转换为字典格式（用于缓存）

        Args:
            entry: SitemapEntry对象

        Returns:
            Dict[str, Any]: 字典格式的条目数据
        """
        try:
            return {
                'url': entry.url,
                'last_modified': entry.last_modified.isoformat() if entry.last_modified else None
            }
        except Exception as e:
            logger.error(f"SitemapEntry序列化失败: {str(e)}", exc_info=True)
            raise

    def _dict_to_sitemap_entry(self, entry_dict: Dict[str, Any]) -> Optional[SitemapEntry]:
        """
        将字典格式转换为SitemapEntry对象（从缓存恢复）

        Args:
            entry_dict: 字典格式的条目数据

        Returns:
            Optional[SitemapEntry]: SitemapEntry对象
        """
        try:
            # 解析时间
            last_modified = None
            if entry_dict.get('last_modified'):
                try:
                    last_modified = datetime.fromisoformat(entry_dict['last_modified'])
                except ValueError:
                    pass

            return SitemapEntry(
                url=entry_dict['url'],
                last_modified=last_modified
            )

        except Exception as e:
            logger.error(f"字典转SitemapEntry失败: {str(e)}", exc_info=True)
            return None

    def clear_cache(self, url: str = None) -> bool:
        """
        清除缓存

        Args:
            url: 指定URL的缓存，如果为None则清除所有缓存

        Returns:
            bool: 是否成功
        """
        try:
            if url:
                # 清除指定URL的缓存
                cache_key = self._generate_cache_key(url)
                success = self.cache.delete(cache_key)
                logger.info(f"清除指定URL缓存: {url}, 成功: {success}")
                return success
            else:
                # 清除所有缓存
                success = self.cache.clear()
                logger.info(f"清除所有Sitemap解析器缓存, 成功: {success}")
                return success
        except Exception as e:
            logger.error(f"清除缓存失败: {str(e)}", exc_info=True)
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
            logger.error(f"获取缓存信息失败: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def is_cache_hit(self, url: str) -> bool:
        """
        检查指定URL是否有缓存

        Args:
            url: Sitemap URL

        Returns:
            bool: 是否有缓存
        """
        try:
            cache_key = self._generate_cache_key(url)
            return self.cache.exists(cache_key)
        except Exception as e:
            logger.error(f"检查缓存失败: {str(e)}", exc_info=True)
            return False

    async def parse_sitemap_content(self, content: str) -> List[SitemapEntry]:
        """
        解析Sitemap内容

        Args:
            content: Sitemap XML/TXT内容

        Returns:
            List[SitemapEntry]: Sitemap条目列表
        """
        try:
            # 检查并修复XML内容格式
            content = content.strip()
            if not content.startswith('<?xml'):
                logger.info("检测到非标准XML格式，尝试修复")
                # 添加XML声明和根元素
                content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1"
        xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
{content}
</urlset>"""
                logger.debug(f"修复后的XML内容:\n{content}")

            # 解析XML
            try:
                root = etree.fromstring(content.encode('utf-8'))
            except etree.XMLSyntaxError as e:
                logger.error(f"XML语法错误: {str(e)}", exc_info=True)
                # 尝试更宽松的解析
                parser = etree.XMLParser(recover=True)
                root = etree.fromstring(content.encode('utf-8'), parser=parser)
                logger.info("使用宽松模式解析XML成功")

            # 检查是否是sitemap索引
            if root.tag.endswith('sitemapindex'):
                logger.info("检测到sitemap索引文件")
                return await self._parse_sitemap_index(root)
            else:
                # 解析普通sitemap
                entries = []
                logger.info("开始解析普通sitemap")

                # 获取所有命名空间
                namespaces = {
                    'ns': root.nsmap.get(None, 'http://www.sitemaps.org/schemas/sitemap/0.9'),
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
                        logger.debug(f"✅ 添加URL成功: {entry.url}, 最后修改: {entry.last_modified}")

                    except Exception as e:
                        logger.error(f"❌ 处理URL元素 {i} 失败: {str(e)}", exc_info=True)
                        invalid_urls += 1
                        continue

                # 输出统计信息
                logger.info(f"Sitemap解析完成:")
                logger.info(f"• 总URL数: {total_urls}")
                logger.info(f"• 有效URL数: {valid_urls}")
                logger.info(f"• 无效URL数: {invalid_urls}")
                logger.info(f"• 时间解析错误: {time_parse_errors}")

                if valid_urls == 0:
                    logger.warning("⚠️ 未找到任何有效的URL")
                elif valid_urls < total_urls:
                    logger.warning(f"⚠️ 部分URL解析失败: {invalid_urls}/{total_urls}")

                return entries

        except Exception as e:
            logger.error(f"解析Sitemap内容失败: {str(e)}", exc_info=True)
            raise


# 便捷函数：创建Sitemap解析器实例
def create_sitemap_parser(timeout: int = 30, max_retries: int = 3, cache_ttl: int = 21600) -> SitemapParser:
    """
    创建Sitemap解析器实例

    Args:
        timeout: 请求超时时间
        max_retries: 最大重试次数
        cache_ttl: 缓存过期时间（秒），默认6小时

    Returns:
        SitemapParser: Sitemap解析器实例
    """
    return SitemapParser(timeout, max_retries, cache_ttl)