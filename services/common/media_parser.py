"""
公共媒体解析器模块

该模块提供跨模块的统一媒体提取功能，避免模块间的直接依赖。
从HTML内容中提取图片和视频等媒体信息。

主要功能：
1. HTML内容解析
2. 图片标签提取
3. 视频标签提取（包括封面图）
4. 媒体URL验证和清理

作者: Assistant
创建时间: 2024年
"""

import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup


class CommonMediaParser:
    """
    公共媒体解析器

    提供跨模块的统一媒体提取功能，避免模块间的直接依赖
    """

    def __init__(self):
        """初始化媒体解析器"""
        self.logger = logging.getLogger(__name__)

    def parse_html_content(self, html_content: str) -> Optional[BeautifulSoup]:
        """
        解析HTML内容

        Args:
            html_content: HTML内容字符串

        Returns:
            Optional[BeautifulSoup]: 解析后的soup对象，失败返回None
        """
        if not html_content:
            return None

        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            self.logger.debug("HTML内容解析成功")
            return soup
        except Exception as e:
            self.logger.error(f"HTML内容解析失败: {str(e)}")
            return None

    def extract_media_from_html(self, html_content: str) -> List[Dict]:
        """
        从HTML内容中提取媒体信息

        Args:
            html_content: HTML内容

        Returns:
            List[Dict]: 媒体信息列表 [{'url': str, 'type': str, 'poster': str}, ...]
                       type 可能是 'image' 或 'video'
                       poster 仅对视频有效，包含封面图URL
        """
        media_list = []
        soup = self.parse_html_content(html_content)

        if not soup:
            self.logger.warning("HTML解析失败，无法提取媒体")
            return media_list

        # 提取图片
        img_tags = soup.find_all('img', src=True)
        self.logger.info(f"提取到 {len(img_tags)} 张图片")

        for img_tag in img_tags:
            img_url = img_tag.get('src', '').strip()
            if not img_url or not img_url.startswith(('http://', 'https://')):
                continue

            # 过滤装饰图片
            if any(keyword in img_url.lower() for keyword in ['icon', 'logo', 'avatar', 'emoji', 'button']):
                self.logger.debug(f"过滤装饰图片: {img_url}")
                continue

            media_list.append({'url': img_url, 'type': 'image'})
            self.logger.debug(f"添加图片: {img_url}")

        # 提取视频
        video_tags = soup.find_all('video', src=True)
        self.logger.info(f"提取到 {len(video_tags)} 个视频")

        for video_tag in video_tags:
            video_url = video_tag.get('src', '').strip()
            poster_url = video_tag.get('poster', '').strip()

            if not video_url or not video_url.startswith(('http://', 'https://')):
                continue

            media_info = {'url': video_url, 'type': 'video'}

            # 添加封面图（如果有效）
            if poster_url and poster_url.startswith(('http://', 'https://')):
                media_info['poster'] = poster_url
                self.logger.debug(f"添加视频(含封面): {video_url} -> {poster_url}")
            else:
                self.logger.debug(f"添加视频(无封面): {video_url}")

            media_list.append(media_info)

        self.logger.info(f"媒体提取完成: {len(media_list)} 个媒体文件")
        return media_list


# 全局解析器实例
_media_parser_instance = None


def get_common_media_parser() -> CommonMediaParser:
    """
    获取公共媒体解析器实例（单例模式）

    Returns:
        CommonMediaParser: 媒体解析器实例
    """
    global _media_parser_instance
    if _media_parser_instance is None:
        _media_parser_instance = CommonMediaParser()
        logging.info("创建公共媒体解析器实例")
    return _media_parser_instance


def extract_media_from_html(html_content: str) -> List[Dict]:
    """
    从HTML内容中提取媒体信息的便捷函数

    Args:
        html_content: HTML内容

    Returns:
        List[Dict]: 媒体信息列表
    """
    parser = get_common_media_parser()
    return parser.extract_media_from_html(html_content)


if __name__ == "__main__":
    # 模块测试代码
    def test_media_parser():
        """测试媒体解析器功能"""
        print("🧪 公共媒体解析器模块测试")

        # 创建解析器
        parser = get_common_media_parser()
        print(f"✅ 创建媒体解析器: {type(parser).__name__}")

        # 测试HTML内容
        test_html = '''
        <div>
            <img src="https://example.com/image1.jpg" alt="测试图片1">
            <img src="https://example.com/image2.png" alt="测试图片2">
            <video src="https://example.com/video1.mp4" poster="https://example.com/poster1.jpg" controls>
                Your browser does not support the video tag.
            </video>
            <video src="https://example.com/video2.mp4" controls>
                Your browser does not support the video tag.
            </video>
        </div>
        '''

        # 提取媒体
        media_list = parser.extract_media_from_html(test_html)
        print(f"✅ 提取到 {len(media_list)} 个媒体项")

        for i, media in enumerate(media_list, 1):
            media_type = "图片" if media['type'] == 'image' else "视频"
            poster_info = f" (封面: {media.get('poster', '无')})" if media['type'] == 'video' else ""
            print(f"  {i}. {media_type}: {media['url']}{poster_info}")

        # 测试便捷函数
        media_list2 = extract_media_from_html(test_html)
        print(f"✅ 便捷函数提取到 {len(media_list2)} 个媒体项")

        print("🎉 公共媒体解析器模块测试完成")

    # 运行测试
    test_media_parser()