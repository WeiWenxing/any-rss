import json
import logging
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import requests
import feedparser
import hashlib


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

    def _is_feed_deleted(self, feed_dir: Path) -> bool:
        """检查Feed是否被标记为删除

        Args:
            feed_dir: Feed存储目录

        Returns:
            bool: 是否被标记为删除
        """
        deleted_file = feed_dir / "deleted.txt"
        return deleted_file.exists()

    def _mark_feed_deleted(self, feed_dir: Path) -> None:
        """标记Feed为已删除

        Args:
            feed_dir: Feed存储目录
        """
        deleted_file = feed_dir / "deleted.txt"
        deleted_file.write_text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        logging.info(f"已标记Feed目录为删除: {feed_dir}")

    def _unmark_feed_deleted(self, feed_dir: Path) -> None:
        """取消Feed的删除标记

        Args:
            feed_dir: Feed存储目录
        """
        deleted_file = feed_dir / "deleted.txt"
        if deleted_file.exists():
            deleted_file.unlink()
            logging.info(f"已取消Feed目录的删除标记: {feed_dir}")

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

            # 检查Feed是否被标记为删除
            if self._is_feed_deleted(feed_dir):
                logging.warning(f"Feed已被标记为删除，跳过下载: {url}")
                return False, "该Feed已被删除", None, []

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
                                f"加载或比较已存在的Feed数据失败 for {url}: {str(e)}"
                            )
                            # 如果加载或比较失败，继续尝试下载
                            pass # 继续执行下载逻辑
                    else:
                        # 如果文件不完整，继续尝试下载
                        pass # 继续执行下载逻辑

            # 下载新文件
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            response = requests.get(url, timeout=10, headers=headers)
            response.raise_for_status() # 检查HTTP请求是否成功

            # 获取原始XML内容
            xml_content = response.text

            # 使用feedparser解析用于验证和比较
            feed_data = feedparser.parse(xml_content)

            if feed_data.bozo:
                # feed_data.bozo 不为0通常表示解析有错误
                logging.warning(
                    f"Feed解析可能存在问题 for {url}: {feed_data.bozo_exception}"
                )
                # 如果是soft error，可以继续；如果是hard error，可能需要返回失败
                if isinstance(
                    feed_data.bozo_exception,
                    (requests.exceptions.RequestException, Exception),
                ):
                     return (
                        False,
                        f"Feed解析失败或下载错误: {feed_data.bozo_exception}",
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
                        f"加载或比较旧的Feed数据失败 for {url} during download: {str(e)}"
                    )
                    # 如果加载或比较失败，new_entries将为空，继续保存新的current文件

            # 保存新下载的XML内容到current文件
            current_feed_file.write_text(xml_content)
            logging.info(f"新Feed数据已保存到: {current_feed_file} for {url}")

            # 更新最后更新日期
            last_update_file.write_text(today)

            return True, "", xml_content, new_entries  # 返回原始XML内容和新增条目

        except requests.exceptions.RequestException as e:
            logging.error(f"下载Feed失败: {url} 原因: {str(e)}")
            return False, f"下载失败: {str(e)}", None, []
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
            logging.error(f"比较Feed条目失败: {str(e)}")
            return []

    def add_feed(self, url: str) -> tuple[bool, str, str | None, list[dict]]:
        """添加Feed监控

        Args:
            url: Feed的URL

        Returns:
            tuple[bool, str, str | None, list[dict]]: (是否成功, 错误信息, 原始XML内容, 新增的条目列表)
        """
        try:
            logging.info(f"尝试添加Feed监控: {url}")

            # 检查是否存在被标记为删除的目录
            feed_dir = self._get_feed_dir(url)
            if self._is_feed_deleted(feed_dir):
                # 如果存在删除标记，取消标记并恢复订阅
                self._unmark_feed_deleted(feed_dir)
                logging.info(f"检测到之前删除的Feed，正在恢复订阅: {url}")

            # 验证是否已存在
            feeds = self.get_feeds()
            is_new_feed = url not in feeds

            if is_new_feed:
                # 如果是新的feed，先尝试下载和解析
                success, error_msg, xml_content, new_entries = self.download_and_parse_feed(url)
                if not success:
                    # 如果下载或解析失败，返回错误，不添加到订阅列表
                    return False, error_msg, None, []

                # 添加到监控列表
                feeds.append(url)
                self.feeds_file.write_text(json.dumps(feeds, indent=2))
                logging.info(f"成功添加Feed监控: {url}")

                # 对于新添加的Feed，返回所有条目而不是新增条目
                if xml_content:
                    try:
                        import feedparser
                        feed_data = feedparser.parse(xml_content)
                        all_entries = list(feed_data.entries)  # 转换为列表
                        logging.info(f"首次添加Feed，返回所有 {len(all_entries)} 个条目")
                        return True, "首次添加", xml_content, all_entries
                    except Exception as e:
                        logging.error(f"解析Feed条目失败: {str(e)}")
                        return True, "添加成功但解析条目失败", xml_content, []
                else:
                    return True, "", xml_content, new_entries
            else:
                # 如果feed已存在，仍然尝试下载和解析（可能是新的一天）
                success, error_msg, xml_content, new_entries = self.download_and_parse_feed(url)
                # 返回下载和解析的结果（只返回新增条目）
                return success, error_msg, xml_content, new_entries

        except Exception as e:
            logging.error(f"添加Feed监控失败: {url}", exc_info=True)
            return False, f"添加失败: {str(e)}", None, []

    def remove_feed(self, url: str) -> tuple[bool, str]:
        """删除RSS订阅（使用标记方式，不真正删除文件）

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
            feeds.remove(url)
            logging.info(f"正在写入RSS订阅到文件: {self.feeds_file}")
            self.feeds_file.write_text(json.dumps(feeds, indent=2))
            logging.info(f"成功从订阅列表中删除RSS订阅: {url}")

            # 标记对应的存储目录为删除状态，而不是真正删除
            try:
                feed_dir = self._get_feed_dir(url)
                if feed_dir.exists():
                    self._mark_feed_deleted(feed_dir)
                    logging.info(f"已标记Feed存储目录为删除: {feed_dir}")
                else:
                    logging.info(f"Feed存储目录不存在，无需标记: {feed_dir}")
            except Exception as e:
                logging.error(f"标记Feed存储目录删除失败: {feed_dir}, 原因: {str(e)}")
                # 即使标记失败，也认为订阅删除成功

            return True, ""
        except Exception as e:
            logging.error(f"删除RSS订阅失败: {url}", exc_info=True)
            return False, f"删除失败: {str(e)}"

    def get_feeds(self) -> list:
        """获取所有监控的feeds"""
        try:
            content = self.feeds_file.read_text()
            return json.loads(content)
        except Exception as e:
            logging.error("读取feeds文件失败", exc_info=True)
            return []
