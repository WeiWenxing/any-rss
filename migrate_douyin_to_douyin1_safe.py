#!/usr/bin/env python3
"""
Douyin到Douyin1安全数据迁移脚本

功能：
1. 智能合并订阅数据（不覆盖现有订阅）
2. 合并已知内容ID（去重处理）
3. 合并消息映射（保留现有映射）
4. 冲突检测和处理
5. 完整的备份和回滚机制

作者: Assistant
创建时间: 2024年
"""

import os
import json
import hashlib
import shutil
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime


class SafeDouyinMigrator:
    """安全的Douyin数据迁移器"""
    
    def __init__(self, dry_run: bool = True):
        """
        初始化安全迁移器
        
        Args:
            dry_run: 是否为试运行模式（不实际修改文件）
        """
        self.dry_run = dry_run
        self.logger = self._setup_logger()
        
        # 源路径（douyin）
        self.source_base = Path("storage/douyin")
        self.source_config = self.source_base / "config"
        self.source_data = self.source_base / "data"
        self.source_media = self.source_base / "media"
        
        # 目标路径（douyin1）
        self.target_base = Path("storage/douyin1")
        self.target_config = self.target_base / "config"
        self.target_data = self.target_base / "data"
        self.target_media = self.target_base / "media"
        
        # 备份路径
        self.backup_base = None
        
        # 迁移统计
        self.stats = {
            "subscriptions_merged": 0,
            "subscriptions_conflicts": 0,
            "known_items_merged": 0,
            "known_items_duplicates": 0,
            "message_mappings_merged": 0,
            "message_mappings_conflicts": 0,
            "directories_created": 0,
            "errors": [],
            "warnings": []
        }
        
        # URL到目录的映射关系
        self.url_directory_mapping = {}
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("safe_douyin_migrator")
        logger.setLevel(logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建文件处理器
        log_file = f"safe_migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def _safe_filename(self, url: str) -> str:
        """
        生成安全的文件名（复用douyin1的逻辑）
        
        Args:
            url: URL字符串
            
        Returns:
            str: 安全的文件名
        """
        # 移除协议前缀
        clean_url = re.sub(r'^https?://', '', url)
        # 替换特殊字符
        clean_url = re.sub(r'[^\w\-_.]', '_', clean_url)
        # 限制长度并添加哈希
        if len(clean_url) > 50:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            clean_url = clean_url[:42] + '_' + url_hash
        
        return clean_url
    
    def _get_douyin_hash(self, url: str) -> str:
        """
        生成douyin模块使用的哈希值
        
        Args:
            url: URL字符串
            
        Returns:
            str: SHA256哈希值前16位
        """
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    
    def _ensure_directories(self):
        """确保目标目录存在"""
        directories = [
            self.target_base,
            self.target_config,
            self.target_data,
            self.target_media
        ]
        
        for directory in directories:
            if not self.dry_run:
                directory.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}确保目录存在: {directory}")
            self.stats["directories_created"] += 1
    
    def _build_url_mapping(self) -> Dict[str, str]:
        """
        构建URL到目录的映射关系
        
        Returns:
            Dict[str, str]: {URL: douyin_hash_dir}
        """
        mapping = {}
        
        if not self.source_data.exists():
            self.logger.warning(f"源数据目录不存在: {self.source_data}")
            return mapping
        
        # 遍历所有哈希目录
        for hash_dir in self.source_data.iterdir():
            if not hash_dir.is_dir():
                continue
                
            url_file = hash_dir / "url.txt"
            if url_file.exists():
                try:
                    url = url_file.read_text(encoding='utf-8').strip()
                    mapping[url] = hash_dir.name
                    self.logger.debug(f"发现URL映射: {url} -> {hash_dir.name}")
                except Exception as e:
                    self.logger.error(f"读取URL文件失败: {url_file}, 错误: {e}")
                    self.stats["errors"].append(f"读取URL文件失败: {url_file}")
        
        self.logger.info(f"构建URL映射完成，共 {len(mapping)} 个URL")
        return mapping
    
    def _load_json_safe(self, file_path: Path) -> Dict:
        """
        安全加载JSON文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            Dict: JSON数据，如果文件不存在或出错则返回空字典
        """
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"加载JSON文件失败: {file_path}, 错误: {e}")
            return {}
    
    def _save_json_safe(self, data: Dict, file_path: Path) -> bool:
        """
        安全保存JSON文件
        
        Args:
            data: 要保存的数据
            file_path: 文件路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            if not self.dry_run:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"保存JSON文件失败: {file_path}, 错误: {e}")
            return False
    
    def create_target_backup(self) -> bool:
        """
        创建目标数据备份（douyin1现有数据）
        
        Returns:
            bool: 是否成功
        """
        try:
            if not self.target_base.exists():
                self.logger.info("目标目录不存在，无需备份")
                return True
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.backup_base = Path(f"storage/douyin1_backup_{timestamp}")
            
            if not self.dry_run:
                shutil.copytree(self.target_base, self.backup_base)
            
            self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}创建目标数据备份: {self.backup_base}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建目标备份失败: {e}", exc_info=True)
            self.stats["errors"].append(f"创建目标备份失败: {e}")
            return False
    
    def merge_subscriptions(self) -> bool:
        """
        智能合并订阅数据
        
        Returns:
            bool: 是否成功
        """
        try:
            self.logger.info("🔄 开始合并订阅数据...")
            
            source_file = self.source_config / "subscriptions.json"
            target_file = self.target_config / "subscriptions.json"
            
            # 加载源数据和目标数据
            source_subs = self._load_json_safe(source_file)
            target_subs = self._load_json_safe(target_file)
            
            self.logger.info(f"源订阅数据: {len(source_subs)} 个URL")
            self.logger.info(f"目标订阅数据: {len(target_subs)} 个URL")
            
            # 合并逻辑
            merged_subs = target_subs.copy()  # 从现有数据开始
            conflicts = []
            
            for url, source_channels in source_subs.items():
                if url in merged_subs:
                    # URL已存在，合并频道列表
                    existing_channels = set(merged_subs[url])
                    new_channels = set(source_channels)
                    
                    # 检查冲突
                    common_channels = existing_channels & new_channels
                    if common_channels:
                        conflicts.append({
                            "url": url,
                            "common_channels": list(common_channels),
                            "source_channels": source_channels,
                            "target_channels": merged_subs[url]
                        })
                        self.logger.warning(f"⚠️ 订阅冲突: {url} 在两个模块中都有相同频道: {list(common_channels)}")
                    
                    # 合并频道（去重）
                    all_channels = existing_channels | new_channels
                    merged_subs[url] = list(all_channels)
                    
                    self.logger.info(f"🔗 合并订阅: {url} ({len(existing_channels)} + {len(new_channels)} -> {len(all_channels)} 个频道)")
                else:
                    # 新URL，直接添加
                    merged_subs[url] = source_channels
                    self.logger.info(f"➕ 新增订阅: {url} ({len(source_channels)} 个频道)")
            
            # 保存合并结果
            if not self._save_json_safe(merged_subs, target_file):
                return False
            
            # 更新统计
            self.stats["subscriptions_merged"] = len(source_subs)
            self.stats["subscriptions_conflicts"] = len(conflicts)
            
            # 记录冲突详情
            if conflicts:
                self.logger.warning(f"⚠️ 发现 {len(conflicts)} 个订阅冲突，详情：")
                for conflict in conflicts:
                    self.logger.warning(f"  URL: {conflict['url']}")
                    self.logger.warning(f"  冲突频道: {conflict['common_channels']}")
                    self.stats["warnings"].append(f"订阅冲突: {conflict['url']} - {conflict['common_channels']}")
            
            self.logger.info(f"✅ 订阅数据合并完成: 总计 {len(merged_subs)} 个URL")
            return True
            
        except Exception as e:
            self.logger.error(f"合并订阅数据失败: {e}", exc_info=True)
            self.stats["errors"].append(f"合并订阅数据失败: {e}")
            return False
    
    def merge_known_items(self) -> bool:
        """
        智能合并已知内容ID数据
        
        Returns:
            bool: 是否成功
        """
        try:
            self.logger.info("🔄 开始合并已知内容数据...")
            
            merged_count = 0
            duplicate_count = 0
            
            for url, hash_dir in self.url_directory_mapping.items():
                source_dir = self.source_data / hash_dir
                source_file = source_dir / "known_item_ids.json"
                
                if not source_file.exists():
                    continue
                
                # 加载源数据
                source_items = self._load_json_safe(source_file)
                if not isinstance(source_items, list):
                    self.logger.warning(f"源已知内容数据格式错误: {source_file}")
                    continue
                
                # 确定目标文件路径
                safe_name = self._safe_filename(url)
                target_dir = self.target_data / safe_name
                target_file = target_dir / "known_item_ids.json"
                
                # 加载目标数据
                target_items = self._load_json_safe(target_file)
                if not isinstance(target_items, list):
                    target_items = []
                
                # 合并已知内容（去重）
                source_set = set(source_items)
                target_set = set(target_items)
                
                duplicates = source_set & target_set
                if duplicates:
                    self.logger.info(f"🔍 发现重复内容: {url} ({len(duplicates)} 个)")
                    duplicate_count += len(duplicates)
                
                # 合并并保持原有顺序
                merged_items = target_items.copy()
                for item in source_items:
                    if item not in target_set:
                        merged_items.append(item)
                
                # 保存合并结果
                if not self.dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)
                
                if not self._save_json_safe(merged_items, target_file):
                    continue
                
                merged_count += 1
                self.logger.info(f"🔗 合并已知内容: {url} ({len(target_items)} + {len(source_items)} -> {len(merged_items)} 个)")
            
            self.stats["known_items_merged"] = merged_count
            self.stats["known_items_duplicates"] = duplicate_count
            
            self.logger.info(f"✅ 已知内容合并完成: {merged_count} 个URL，{duplicate_count} 个重复项")
            return True
            
        except Exception as e:
            self.logger.error(f"合并已知内容失败: {e}", exc_info=True)
            self.stats["errors"].append(f"合并已知内容失败: {e}")
            return False
    
    def merge_message_mappings(self) -> bool:
        """
        智能合并消息映射数据
        
        Returns:
            bool: 是否成功
        """
        try:
            self.logger.info("🔄 开始合并消息映射数据...")
            
            source_file = self.source_config / "message_mappings.json"
            target_file = self.target_config / "message_mappings.json"
            
            # 加载源数据和目标数据
            source_mappings = self._load_json_safe(source_file)
            target_mappings = self._load_json_safe(target_file)
            
            self.logger.info(f"源消息映射: {len(source_mappings)} 个URL")
            self.logger.info(f"目标消息映射: {len(target_mappings)} 个URL")
            
            # 合并逻辑
            merged_mappings = target_mappings.copy()  # 从现有数据开始
            conflicts = []
            
            for url, source_url_mappings in source_mappings.items():
                if url in merged_mappings:
                    # URL已存在，合并item映射
                    existing_mappings = merged_mappings[url]
                    
                    for item_id, source_item_mappings in source_url_mappings.items():
                        if item_id in existing_mappings:
                            # item_id已存在，合并频道映射
                            existing_item_mappings = existing_mappings[item_id]
                            
                            for chat_id, source_msg_ids in source_item_mappings.items():
                                if chat_id in existing_item_mappings:
                                    # 频道已存在，检查冲突
                                    existing_msg_ids = existing_item_mappings[chat_id]
                                    if existing_msg_ids != source_msg_ids:
                                        conflicts.append({
                                            "url": url,
                                            "item_id": item_id,
                                            "chat_id": chat_id,
                                            "source_msg_ids": source_msg_ids,
                                            "target_msg_ids": existing_msg_ids
                                        })
                                        self.logger.warning(f"⚠️ 消息映射冲突: {url}/{item_id}/{chat_id}")
                                        # 保持现有映射，不覆盖
                                    else:
                                        self.logger.debug(f"消息映射一致: {url}/{item_id}/{chat_id}")
                                else:
                                    # 新频道，直接添加
                                    existing_item_mappings[chat_id] = source_msg_ids
                        else:
                            # 新item_id，直接添加
                            existing_mappings[item_id] = source_item_mappings
                else:
                    # 新URL，直接添加
                    merged_mappings[url] = source_url_mappings
                    self.logger.info(f"➕ 新增消息映射: {url}")
            
            # 保存合并结果
            if not self._save_json_safe(merged_mappings, target_file):
                return False
            
            # 更新统计
            self.stats["message_mappings_merged"] = len(source_mappings)
            self.stats["message_mappings_conflicts"] = len(conflicts)
            
            # 记录冲突详情
            if conflicts:
                self.logger.warning(f"⚠️ 发现 {len(conflicts)} 个消息映射冲突，保持现有映射")
                for conflict in conflicts:
                    self.logger.warning(f"  {conflict['url']}/{conflict['item_id']}/{conflict['chat_id']}")
                    self.stats["warnings"].append(f"消息映射冲突: {conflict['url']}/{conflict['item_id']}/{conflict['chat_id']}")
            
            self.logger.info(f"✅ 消息映射合并完成: 总计 {len(merged_mappings)} 个URL")
            return True
            
        except Exception as e:
            self.logger.error(f"合并消息映射失败: {e}", exc_info=True)
            self.stats["errors"].append(f"合并消息映射失败: {e}")
            return False
    
    def detect_conflicts(self) -> Dict[str, List]:
        """
        检测潜在冲突
        
        Returns:
            Dict[str, List]: 冲突报告
        """
        conflicts = {
            "subscription_conflicts": [],
            "directory_conflicts": [],
            "url_conflicts": []
        }
        
        try:
            self.logger.info("🔍 检测潜在冲突...")
            
            # 检查订阅冲突
            source_subs = self._load_json_safe(self.source_config / "subscriptions.json")
            target_subs = self._load_json_safe(self.target_config / "subscriptions.json")
            
            for url in source_subs:
                if url in target_subs:
                    source_channels = set(source_subs[url])
                    target_channels = set(target_subs[url])
                    common_channels = source_channels & target_channels
                    
                    if common_channels:
                        conflicts["subscription_conflicts"].append({
                            "url": url,
                            "common_channels": list(common_channels),
                            "source_only": list(source_channels - target_channels),
                            "target_only": list(target_channels - source_channels)
                        })
            
            # 检查目录冲突
            for url in self.url_directory_mapping:
                safe_name = self._safe_filename(url)
                target_dir = self.target_data / safe_name
                
                if target_dir.exists():
                    conflicts["directory_conflicts"].append({
                        "url": url,
                        "safe_name": safe_name,
                        "target_dir": str(target_dir)
                    })
            
            # 汇总报告
            total_conflicts = (len(conflicts["subscription_conflicts"]) + 
                             len(conflicts["directory_conflicts"]) + 
                             len(conflicts["url_conflicts"]))
            
            if total_conflicts > 0:
                self.logger.warning(f"⚠️ 检测到 {total_conflicts} 个潜在冲突")
                self.logger.warning(f"  - 订阅冲突: {len(conflicts['subscription_conflicts'])} 个")
                self.logger.warning(f"  - 目录冲突: {len(conflicts['directory_conflicts'])} 个")
                self.logger.warning(f"  - URL冲突: {len(conflicts['url_conflicts'])} 个")
            else:
                self.logger.info("✅ 未检测到冲突")
            
            return conflicts
            
        except Exception as e:
            self.logger.error(f"检测冲突失败: {e}", exc_info=True)
            return conflicts
    
    def rollback_changes(self) -> bool:
        """
        回滚更改（恢复备份）
        
        Returns:
            bool: 是否成功
        """
        try:
            if not self.backup_base or not self.backup_base.exists():
                self.logger.error("没有找到备份数据，无法回滚")
                return False
            
            self.logger.info(f"🔄 开始回滚更改，恢复备份: {self.backup_base}")
            
            # 删除当前目标目录
            if self.target_base.exists():
                shutil.rmtree(self.target_base)
            
            # 恢复备份
            shutil.copytree(self.backup_base, self.target_base)
            
            self.logger.info("✅ 回滚完成")
            return True
            
        except Exception as e:
            self.logger.error(f"回滚失败: {e}", exc_info=True)
            return False
    
    def run_safe_migration(self, create_backup: bool = True) -> bool:
        """
        执行安全迁移流程
        
        Args:
            create_backup: 是否创建备份
            
        Returns:
            bool: 是否成功
        """
        self.logger.info(f"🛡️ 开始安全数据迁移 {'(试运行模式)' if self.dry_run else '(实际执行)'}")
        
        try:
            # 1. 创建目标数据备份
            if create_backup:
                if not self.create_target_backup():
                    return False
            
            # 2. 确保目标目录存在
            self._ensure_directories()
            
            # 3. 构建URL映射
            self.url_directory_mapping = self._build_url_mapping()
            
            # 4. 检测冲突
            conflicts = self.detect_conflicts()
            
            # 5. 合并订阅数据
            if not self.merge_subscriptions():
                return False
            
            # 6. 合并已知内容
            if not self.merge_known_items():
                return False
            
            # 7. 合并消息映射
            if not self.merge_message_mappings():
                return False
            
            # 8. 输出统计信息
            self.print_statistics()
            
            self.logger.info("🎉 安全数据迁移完成！")
            return True
            
        except Exception as e:
            self.logger.error(f"安全迁移过程中发生错误: {e}", exc_info=True)
            
            # 尝试回滚
            if not self.dry_run and self.backup_base:
                self.logger.info("🔄 尝试回滚更改...")
                self.rollback_changes()
            
            return False
    
    def print_statistics(self):
        """打印迁移统计信息"""
        self.logger.info("=" * 60)
        self.logger.info("📊 安全迁移统计信息")
        self.logger.info("=" * 60)
        self.logger.info(f"订阅数据合并: {self.stats['subscriptions_merged']} 个")
        self.logger.info(f"订阅冲突处理: {self.stats['subscriptions_conflicts']} 个")
        self.logger.info(f"已知内容合并: {self.stats['known_items_merged']} 个URL")
        self.logger.info(f"重复内容去除: {self.stats['known_items_duplicates']} 个")
        self.logger.info(f"消息映射合并: {self.stats['message_mappings_merged']} 个")
        self.logger.info(f"消息映射冲突: {self.stats['message_mappings_conflicts']} 个")
        self.logger.info(f"创建目录数量: {self.stats['directories_created']} 个")
        self.logger.info(f"错误数量: {len(self.stats['errors'])} 个")
        self.logger.info(f"警告数量: {len(self.stats['warnings'])} 个")
        
        if self.stats['errors']:
            self.logger.info("\n❌ 错误详情:")
            for error in self.stats['errors']:
                self.logger.info(f"  - {error}")
        
        if self.stats['warnings']:
            self.logger.info("\n⚠️ 警告详情:")
            for warning in self.stats['warnings']:
                self.logger.info(f"  - {warning}")
        
        self.logger.info("=" * 60)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Douyin到Douyin1安全数据迁移工具')
    parser.add_argument('--dry-run', action='store_true', 
                       help='试运行模式，不实际修改文件')
    parser.add_argument('--no-backup', action='store_true',
                       help='不创建备份')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    parser.add_argument('--rollback', type=str, metavar='BACKUP_DIR',
                       help='回滚到指定备份目录')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 处理回滚请求
    if args.rollback:
        backup_path = Path(args.rollback)
        if not backup_path.exists():
            print(f"❌ 备份目录不存在: {backup_path}")
            exit(1)
        
        try:
            target_path = Path("storage/douyin1")
            if target_path.exists():
                shutil.rmtree(target_path)
            shutil.copytree(backup_path, target_path)
            print(f"✅ 回滚完成: {backup_path} -> {target_path}")
            exit(0)
        except Exception as e:
            print(f"❌ 回滚失败: {e}")
            exit(1)
    
    # 创建安全迁移器
    migrator = SafeDouyinMigrator(dry_run=args.dry_run)
    
    # 执行安全迁移
    success = migrator.run_safe_migration(create_backup=not args.no_backup)
    
    if success:
        print("✅ 安全迁移完成！")
        if args.dry_run:
            print("💡 这是试运行模式，要实际执行请移除 --dry-run 参数")
        else:
            print("💾 已创建备份，如需回滚请使用 --rollback 参数")
    else:
        print("❌ 安全迁移失败！请检查日志文件")
        exit(1)


if __name__ == "__main__":
    main() 