"""
RSS解析工具模块
统一管理HTML和XML解析逻辑，避免重复和混乱
"""

import logging
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
from .config import get_parser_config


class UnifiedParser:
    """统一解析器类"""

    def __init__(self):
        self.config = get_parser_config()

    def parse_html_content(self, html_content: str) -> Optional[BeautifulSoup]:
        """
        解析HTML内容（用于提取媒体标签等）

        Args:
            html_content: HTML内容字符串

        Returns:
            Optional[BeautifulSoup]: 解析后的soup对象，失败返回None
        """
        if not html_content:
            return None

        try:
            soup = BeautifulSoup(html_content, self.config.HTML_PARSER)
            logging.debug(f"HTML内容解析成功，使用解析器: {self.config.HTML_PARSER}")
            return soup
        except Exception as e:
            logging.error(f"HTML内容解析失败: {str(e)}")
            return None

    def parse_xml_fragment(self, xml_content: str) -> Optional[BeautifulSoup]:
        """
        解析XML片段（用于RSS/Atom条目等）

        Args:
            xml_content: XML内容字符串

        Returns:
            Optional[BeautifulSoup]: 解析后的soup对象，失败返回None
        """
        if not xml_content:
            return None

        # 按优先级尝试不同的解析器
        for parser in self.config.XML_PARSERS:
            try:
                soup = BeautifulSoup(xml_content, parser)
                logging.debug(f"XML片段解析成功，使用解析器: {parser}")
                return soup
            except Exception as e:
                logging.warning(f"解析器 {parser} 失败: {str(e)}")
                continue

        logging.error("所有XML解析器都失败了")
        return None

    def extract_media_from_html(self, html_content: str) -> List[Dict]:
        """
        从HTML内容中提取媒体信息

        Args:
            html_content: HTML内容

        Returns:
            List[Dict]: 媒体信息列表 [{'url': str, 'type': str, 'poster': str}, ...]
        """
        media_list = []
        soup = self.parse_html_content(html_content)

        if not soup:
            logging.warning("HTML解析失败，无法提取媒体")
            return media_list

        # 提取图片
        img_tags = soup.find_all('img', src=True)
        logging.info(f"提取到 {len(img_tags)} 张图片")

        for img_tag in img_tags:
            img_url = img_tag.get('src', '').strip()
            if not img_url or not img_url.startswith(('http://', 'https://')):
                continue

            # 过滤装饰图片
            if any(keyword in img_url.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'button']):
                logging.debug(f"过滤装饰图片: {img_url}")
                continue

            media_list.append({'url': img_url, 'type': 'image'})
            logging.debug(f"添加图片: {img_url}")

        # 提取视频
        video_tags = soup.find_all('video', src=True)
        logging.info(f"提取到 {len(video_tags)} 个视频")

        for video_tag in video_tags:
            video_url = video_tag.get('src', '').strip()
            poster_url = video_tag.get('poster', '').strip()

            if not video_url or not video_url.startswith(('http://', 'https://')):
                continue

            media_info = {'url': video_url, 'type': 'video'}

            # 添加封面图（如果有效）
            if poster_url and poster_url.startswith(('http://', 'https://')):
                media_info['poster'] = poster_url
                logging.debug(f"添加视频(含封面): {video_url} -> {poster_url}")
            else:
                logging.debug(f"添加视频(无封面): {video_url}")

            media_list.append(media_info)

        logging.info(f"媒体提取完成: {len(media_list)} 个媒体文件")
        return media_list

    def extract_entry_data_from_xml(self, xml_content: str) -> Optional[Dict]:
        """
        从XML片段中提取条目数据（仅用于调试命令）

        Args:
            xml_content: XML内容

        Returns:
            Optional[Dict]: 提取的条目数据，失败返回None
        """
        soup = self.parse_xml_fragment(xml_content)
        if not soup:
            return None

        # 检测格式类型
        is_atom = xml_content.strip().startswith('<entry')
        format_type = "Atom" if is_atom else "RSS"

        entry_data = {
            'title': '无标题',
            'description': '',
            'summary': '',
            'link': '',
            'published': '',
            'author': '',
            'id': '',
            'format_type': format_type
        }

        # 提取标题
        title_tag = soup.find('title')
        if title_tag:
            entry_data['title'] = title_tag.get_text().strip()

        # 提取内容（支持RSS的description和Atom的content）
        content_tag = soup.find('content') or soup.find('description')
        if content_tag:
            desc_content = content_tag.decode_contents() if content_tag.contents else content_tag.get_text()
            entry_data['description'] = desc_content.strip()
            entry_data['summary'] = entry_data['description']

        # 提取链接
        link_tag = soup.find('link')
        if link_tag:
            if link_tag.get('href'):  # Atom格式
                entry_data['link'] = link_tag.get('href').strip()
            elif link_tag.get_text():  # RSS格式
                entry_data['link'] = link_tag.get_text().strip()

        # 提取发布时间
        pubdate_tag = (soup.find('pubDate') or soup.find('pubdate') or
                      soup.find('published') or soup.find('updated'))
        if pubdate_tag:
            entry_data['published'] = pubdate_tag.get_text().strip()

        # 提取作者
        author_tag = soup.find('author')
        if author_tag:
            name_tag = author_tag.find('name')
            if name_tag:  # Atom格式
                entry_data['author'] = name_tag.get_text().strip()
            else:  # RSS格式
                entry_data['author'] = author_tag.get_text().strip()

        # 提取ID
        id_tag = soup.find('id') or soup.find('guid')
        if id_tag:
            entry_data['id'] = id_tag.get_text().strip()

        logging.info(f"XML条目解析成功: {format_type}格式, 标题: {entry_data['title']}")
        return entry_data


# 全局解析器实例
_parser_instance = None

def get_unified_parser() -> UnifiedParser:
    """获取统一解析器实例（单例模式）"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = UnifiedParser()
        logging.info("✅ 统一解析器初始化完成")
    return _parser_instance