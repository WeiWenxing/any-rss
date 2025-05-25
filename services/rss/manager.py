import json
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import feedparser
import hashlib
from .network_utils import get_network_manager


class RSSManager:
    def __init__(self):
        self.config_dir = Path("storage/rss/config")
        self.feeds_data_dir = Path("storage/rss/feeds_data")
        self.feeds_file = self.config_dir / "feeds.json"
        self._init_directories()

    def _get_feed_dir(self, url: str) -> Path:
        """根据URL生成唯一的目录名

        Args:
            url: Feed的URL

        Returns:
            Path: 对应的目录路径
        """
        # 使用URL的SHA256哈希值作为目录名
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]  # 取前16位作为目录名
        feed_dir = self.feeds_data_dir / url_hash
        feed_dir.mkdir(parents=True, exist_ok=True)

        # 保存原始URL到文件
        url_file = feed_dir / "url.txt"
        if not url_file.exists():
            url_file.write_text(url)

        return feed_dir

    def _init_directories(self):
        """初始化必要的目录"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.feeds_data_dir.mkdir(parents=True, exist_ok=True)

        if not self.feeds_file.exists():
            self.feeds_file.write_text("[]")

    def download_and_parse_feed(
        self, url: str
    ) -> tuple[bool, str, str | None, list[dict]]:
        """下载并解析Feed文件，返回新增的条目列表

        Args:
            url: Feed的URL

        Returns:
            tuple[bool, str, str | None, list[dict]]: (是否成功, 错误信息, 原始XML内容, 新增的条目列表)
        """
        try:
            logging.info(f"尝试下载并解析Feed: {url}")
            feed_dir = self._get_feed_dir(url)

            # 检查今天是否已经更新过
            last_update_file = feed_dir / "last_update.txt"
            today = datetime.now().strftime("%Y%m%d")

            if last_update_file.exists():
                last_date = last_update_file.read_text().strip()
                if last_date == today:
                    # 如果今天已经更新过，尝试加载之前的XML进行比较
                    current_feed_file = feed_dir / "feed-current.xml"
                    latest_feed_file = feed_dir / "feed-latest.xml"
                    if current_feed_file.exists() and latest_feed_file.exists():
                        try:
                            current_xml = current_feed_file.read_text()
                            latest_xml = latest_feed_file.read_text()
                            new_entries = self.compare_feeds(current_xml, latest_xml)
                            # 返回True表示成功，但信息提示今天已更新，并提供已找到的新条目
                            return (True, "今天已经更新过此Feed", current_xml, new_entries)
                        except Exception as e:
                            logging.error(
                                f"加载或比较已存在的Feed数据失败 for {url}: {str(e)}", exc_info=True
                            )
                            # 如果加载或比较失败，继续尝试下载
                            pass # 继续执行下载逻辑
                    else:
                        # 如果文件不完整，继续尝试下载
                        pass # 继续执行下载逻辑

            # 下载新文件
            network_manager = get_network_manager()
            success, error_msg, xml_content = network_manager.download_feed(url, use_cache=False)

            if not success:
                return False, error_msg, None, []

            # 使用feedparser解析用于验证和比较
            feed_data = feedparser.parse(xml_content)

            if feed_data.bozo:
                # feed_data.bozo 不为0通常表示解析有错误
                logging.warning(
                    f"Feed解析可能存在问题 for {url}: {feed_data.bozo_exception}"
                )
                # 如果是严重的解析错误，返回失败
                if isinstance(feed_data.bozo_exception, Exception):
                    # 对于XML解析错误等严重问题，返回失败
                    error_type = type(feed_data.bozo_exception).__name__
                    if error_type in ['XMLSyntaxError', 'ExpatError', 'SAXParseException']:
                        return (
                            False,
                            f"Feed解析失败: {feed_data.bozo_exception}",
                            None,
                            [],
                        )

            # 比较新旧条目
            new_entries = []
            current_feed_file = feed_dir / "feed-current.xml"
            latest_feed_file = feed_dir / "feed-latest.xml"

            # 如果存在current文件，将其内容作为latest
            if current_feed_file.exists():
                try:
                    old_xml = current_feed_file.read_text()
                    # 比较新下载的XML和之前的XML
                    new_entries = self.compare_feeds(xml_content, old_xml)
                    # 将原来的current文件重命名为latest
                    current_feed_file.replace(latest_feed_file)
                    logging.info(f"已将旧的current feed文件重命名为latest for {url}")
                except Exception as e:
                    logging.error(
                        f"加载或比较旧的Feed数据失败 for {url} during download: {str(e)}", exc_info=True
                    )
                    # 如果加载或比较失败，new_entries将为空，继续保存新的current文件

            # 保存新下载的XML内容到current文件
            current_feed_file.write_text(xml_content)
            logging.info(f"新Feed数据已保存到: {current_feed_file} for {url}")

            # 更新最后更新日期
            last_update_file.write_text(today)

            return True, "", xml_content, new_entries  # 返回原始XML内容和新增条目

        except Exception as e:
            logging.error(f"处理Feed失败: {url} 原因: {str(e)}", exc_info=True)
            return False, f"处理失败: {str(e)}", None, []

    def compare_feeds(self, current_xml: str, old_xml: str) -> list[dict]:
        """比较新旧Feed XML内容，返回新增的条目列表

        Args:
            current_xml: 当前的Feed XML内容
            old_xml: 旧的Feed XML内容

        Returns:
            list[dict]: 新增的条目列表
        """
        try:
            # 使用feedparser解析XML
            current_feed = feedparser.parse(current_xml)
            old_feed = feedparser.parse(old_xml)

            # 将旧条目转换为集合以便快速查找
            # 尝试使用条目的 'id' 或 'link' 作为唯一标识
            old_entries_set = set()
            for entry in old_feed.entries:
                # 优先使用id，如果不存在则使用link
                unique_id = entry.get('id', entry.get('link'))
                if unique_id:
                    old_entries_set.add(unique_id)
                else:
                    # 如果id和link都不存在，尝试使用标题作为标识（不够可靠）
                    old_entries_set.add(entry.get('title', str(entry))) # 使用str(entry)作为fallback

            new_entries = []
            for entry in current_feed.entries:
                unique_id = entry.get('id', entry.get('link'))
                # 如果能找到唯一标识，且该标识不在旧条目集合中，则认为是新条目
                if unique_id and unique_id not in old_entries_set:
                    new_entries.append(entry)
                # 如果没有唯一标识，并且整个条目（转为字符串）不在旧条目集合中，也认为是新条目
                elif not unique_id and str(entry) not in old_entries_set:
                     new_entries.append(entry)

            logging.info(f"比较Feed完成，发现 {len(new_entries)} 个新条目")
            return new_entries
        except Exception as e:
            logging.error(f"比较Feed条目失败: {str(e)}", exc_info=True)
            return []

    def add_feed(self, url: str, chat_id: str = None) -> tuple[bool, str, str | None, list[dict]]:
        """添加Feed监控

        Args:
            url: Feed的URL
            chat_id: 目标频道ID，如果为None则使用默认频道

        Returns:
            tuple[bool, str, str | None, list[dict]]: (是否成功, 错误信息, 原始XML内容, 新增的条目列表)
        """
        try:
            logging.info(f"尝试添加Feed监控: {url} -> 频道: {chat_id}")

            # 验证是否已存在
            feeds = self.get_feeds()
            is_new_feed = url not in feeds

            if is_new_feed:
                # 如果是新的feed，先尝试下载和解析
                success, error_msg, xml_content, new_entries = self.download_and_parse_feed(url)
                if not success:
                    # 如果下载或解析失败，返回错误，不添加到订阅列表
                    return False, error_msg, None, []

                # 添加到监控列表（URL -> 频道ID映射）
                feeds[url] = chat_id
                self.feeds_file.write_text(json.dumps(feeds, indent=2))
                logging.info(f"成功添加Feed监控: {url} -> 频道: {chat_id}")

                # 对于新添加的Feed，返回所有条目而不是新增条目
                if xml_content:
                    try:
                        import feedparser
                        feed_data = feedparser.parse(xml_content)
                        all_entries = list(feed_data.entries)  # 转换为列表
                        logging.info(f"首次添加Feed，返回所有 {len(all_entries)} 个条目")
                        return True, "首次添加", xml_content, all_entries
                    except Exception as e:
                        logging.error(f"解析Feed条目失败: {str(e)}", exc_info=True)
                        return True, "添加成功但解析条目失败", xml_content, []
                else:
                    return True, "", xml_content, new_entries
            else:
                # 如果feed已存在，更新频道ID
                old_chat_id = feeds[url]
                feeds[url] = chat_id
                self.feeds_file.write_text(json.dumps(feeds, indent=2))
                logging.info(f"更新Feed频道: {url} 从 {old_chat_id} 改为 {chat_id}")

                # 仍然尝试下载和解析（可能是新的一天）
                success, error_msg, xml_content, new_entries = self.download_and_parse_feed(url)
                # 返回下载和解析的结果（只返回新增条目）
                return success, error_msg, xml_content, new_entries

        except Exception as e:
            logging.error(f"添加Feed监控失败: {url}", exc_info=True)
            return False, f"添加失败: {str(e)}", None, []

    def remove_feed(self, url: str) -> tuple[bool, str]:
        """删除RSS订阅（只删除配置记录，保留文件数据）

        Args:
            url: RSS订阅链接

        Returns:
            tuple[bool, str]: (是否删除成功, 错误信息)
        """
        try:
            logging.info(f"尝试删除RSS订阅: {url}")
            feeds = self.get_feeds()

            if url not in feeds:
                logging.warning(f"RSS订阅不存在: {url}")
                return False, "该RSS订阅不存在"

            # 从订阅列表中移除
            chat_id = feeds.pop(url)
            logging.info(f"正在写入RSS订阅到文件: {self.feeds_file}")
            self.feeds_file.write_text(json.dumps(feeds, indent=2))
            logging.info(f"成功从订阅列表中删除RSS订阅: {url} (原频道: {chat_id})")

            # 不再标记文件删除，保留所有数据文件
            logging.info(f"RSS订阅配置已删除，数据文件已保留: {url}")

            return True, ""
        except Exception as e:
            logging.error(f"删除RSS订阅失败: {url}", exc_info=True)
            return False, f"删除失败: {str(e)}"

    def get_feeds(self) -> dict:
        """获取所有监控的feeds

        Returns:
            dict: {url: chat_id} 格式的订阅字典
        """
        try:
            content = self.feeds_file.read_text()
            data = json.loads(content)

            # 兼容旧格式：如果是列表，转换为字典
            if isinstance(data, list):
                logging.info("检测到旧格式的feeds.json，正在转换为新格式")
                # 将列表转换为字典，使用None作为默认频道ID
                feeds_dict = {url: None for url in data}
                # 保存新格式
                self.feeds_file.write_text(json.dumps(feeds_dict, indent=2))
                logging.info(f"已转换 {len(data)} 个订阅到新格式")
                return feeds_dict

            return data
        except Exception as e:
            logging.error("读取feeds文件失败", exc_info=True)
            return {}

    def get_feed_chat_id(self, url: str) -> str | None:
        """获取指定Feed的目标频道ID

        Args:
            url: Feed的URL

        Returns:
            str | None: 频道ID，如果不存在则返回None
        """
        feeds = self.get_feeds()
        return feeds.get(url)
