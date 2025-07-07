#!/usr/bin/env python3
"""
Douyin到Douyin1数据迁移脚本

功能：
1. 迁移订阅数据 (subscriptions.json)
2. 迁移已知内容ID (known_item_ids.json)
3. 迁移消息映射 (message_mappings.json)
4. 建立URL到目录的映射关系
5. 验证迁移结果

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
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class DouyinMigrator:
    """Douyin数据迁移器"""
    
    def __init__(self, dry_run: bool = True):
        """
        初始化迁移器
        
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
        
        # 迁移统计
        self.stats = {
            "subscriptions_migrated": 0,
            "known_items_migrated": 0,
            "message_mappings_migrated": 0,
            "directories_created": 0,
            "errors": []
        }
        
        # URL到目录的映射关系
        self.url_directory_mapping = {}
        
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger("douyin_migrator")
        logger.setLevel(logging.INFO)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 创建文件处理器
        log_file = f"migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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
            self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}创建目录: {directory}")
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
    
    def migrate_subscriptions(self) -> bool:
        """
        迁移订阅数据
        
        Returns:
            bool: 是否成功
        """
        try:
            source_file = self.source_config / "subscriptions.json"
            target_file = self.target_config / "subscriptions.json"
            
            if not source_file.exists():
                self.logger.warning(f"源订阅文件不存在: {source_file}")
                return True
            
            # 读取源数据
            with open(source_file, 'r', encoding='utf-8') as f:
                subscriptions = json.load(f)
            
            self.logger.info(f"读取到 {len(subscriptions)} 个订阅")
            
            # 验证数据格式
            for url, channels in subscriptions.items():
                if not isinstance(channels, list):
                    self.logger.error(f"订阅数据格式错误: {url} -> {channels}")
                    return False
            
            # 写入目标文件
            if not self.dry_run:
                with open(target_file, 'w', encoding='utf-8') as f:
                    json.dump(subscriptions, f, ensure_ascii=False, indent=2)
            
            self.stats["subscriptions_migrated"] = len(subscriptions)
            self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}订阅数据迁移完成: {len(subscriptions)} 个")
            return True
            
        except Exception as e:
            self.logger.error(f"迁移订阅数据失败: {e}", exc_info=True)
            self.stats["errors"].append(f"迁移订阅数据失败: {e}")
            return False
    
    def migrate_known_items(self) -> bool:
        """
        迁移已知内容ID数据
        
        Returns:
            bool: 是否成功
        """
        try:
            migrated_count = 0
            
            for url, hash_dir in self.url_directory_mapping.items():
                source_dir = self.source_data / hash_dir
                source_file = source_dir / "known_item_ids.json"
                
                if not source_file.exists():
                    self.logger.debug(f"已知内容文件不存在: {source_file}")
                    continue
                
                # 读取源数据
                with open(source_file, 'r', encoding='utf-8') as f:
                    known_items = json.load(f)
                
                # 创建目标目录
                safe_name = self._safe_filename(url)
                target_dir = self.target_data / safe_name
                target_file = target_dir / "known_item_ids.json"
                
                if not self.dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    with open(target_file, 'w', encoding='utf-8') as f:
                        json.dump(known_items, f, ensure_ascii=False, indent=2)
                
                migrated_count += 1
                self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}迁移已知内容: {url} ({len(known_items)} 个)")
            
            self.stats["known_items_migrated"] = migrated_count
            self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}已知内容迁移完成: {migrated_count} 个URL")
            return True
            
        except Exception as e:
            self.logger.error(f"迁移已知内容失败: {e}", exc_info=True)
            self.stats["errors"].append(f"迁移已知内容失败: {e}")
            return False
    
    def migrate_message_mappings(self) -> bool:
        """
        迁移消息映射数据
        
        Returns:
            bool: 是否成功
        """
        try:
            source_file = self.source_config / "message_mappings.json"
            target_file = self.target_config / "message_mappings.json"
            
            if not source_file.exists():
                self.logger.warning(f"源消息映射文件不存在: {source_file}")
                # 创建空的消息映射文件
                if not self.dry_run:
                    with open(target_file, 'w', encoding='utf-8') as f:
                        json.dump({}, f, ensure_ascii=False, indent=2)
                return True
            
            # 读取源数据
            with open(source_file, 'r', encoding='utf-8') as f:
                message_mappings = json.load(f)
            
            self.logger.info(f"读取到 {len(message_mappings)} 个消息映射")
            
            # 写入目标文件
            if not self.dry_run:
                with open(target_file, 'w', encoding='utf-8') as f:
                    json.dump(message_mappings, f, ensure_ascii=False, indent=2)
            
            self.stats["message_mappings_migrated"] = len(message_mappings)
            self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}消息映射迁移完成: {len(message_mappings)} 个")
            return True
            
        except Exception as e:
            self.logger.error(f"迁移消息映射失败: {e}", exc_info=True)
            self.stats["errors"].append(f"迁移消息映射失败: {e}")
            return False
    
    def verify_migration(self) -> bool:
        """
        验证迁移结果
        
        Returns:
            bool: 验证是否通过
        """
        try:
            self.logger.info("开始验证迁移结果...")
            
            # 验证订阅数据
            source_subs_file = self.source_config / "subscriptions.json"
            target_subs_file = self.target_config / "subscriptions.json"
            
            if source_subs_file.exists() and target_subs_file.exists():
                with open(source_subs_file, 'r', encoding='utf-8') as f:
                    source_subs = json.load(f)
                with open(target_subs_file, 'r', encoding='utf-8') as f:
                    target_subs = json.load(f)
                
                if source_subs == target_subs:
                    self.logger.info("✅ 订阅数据验证通过")
                else:
                    self.logger.error("❌ 订阅数据验证失败")
                    return False
            
            # 验证已知内容数据
            verified_count = 0
            for url, hash_dir in self.url_directory_mapping.items():
                source_file = self.source_data / hash_dir / "known_item_ids.json"
                if not source_file.exists():
                    continue
                
                safe_name = self._safe_filename(url)
                target_file = self.target_data / safe_name / "known_item_ids.json"
                
                if target_file.exists():
                    with open(source_file, 'r', encoding='utf-8') as f:
                        source_items = json.load(f)
                    with open(target_file, 'r', encoding='utf-8') as f:
                        target_items = json.load(f)
                    
                    if source_items == target_items:
                        verified_count += 1
                    else:
                        self.logger.error(f"❌ 已知内容数据验证失败: {url}")
                        return False
            
            self.logger.info(f"✅ 已知内容数据验证通过: {verified_count} 个URL")
            
            # 验证消息映射
            source_msg_file = self.source_config / "message_mappings.json"
            target_msg_file = self.target_config / "message_mappings.json"
            
            if source_msg_file.exists() and target_msg_file.exists():
                with open(source_msg_file, 'r', encoding='utf-8') as f:
                    source_msgs = json.load(f)
                with open(target_msg_file, 'r', encoding='utf-8') as f:
                    target_msgs = json.load(f)
                
                if source_msgs == target_msgs:
                    self.logger.info("✅ 消息映射验证通过")
                else:
                    self.logger.error("❌ 消息映射验证失败")
                    return False
            
            self.logger.info("✅ 所有数据验证通过")
            return True
            
        except Exception as e:
            self.logger.error(f"验证迁移结果失败: {e}", exc_info=True)
            return False
    
    def create_backup(self) -> bool:
        """
        创建源数据备份
        
        Returns:
            bool: 是否成功
        """
        try:
            if not self.source_base.exists():
                self.logger.warning(f"源目录不存在: {self.source_base}")
                return True
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = Path(f"storage/douyin_backup_{timestamp}")
            
            if not self.dry_run:
                shutil.copytree(self.source_base, backup_dir)
            
            self.logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}创建备份: {backup_dir}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建备份失败: {e}", exc_info=True)
            self.stats["errors"].append(f"创建备份失败: {e}")
            return False
    
    def run_migration(self, create_backup: bool = True) -> bool:
        """
        执行完整迁移流程
        
        Args:
            create_backup: 是否创建备份
            
        Returns:
            bool: 是否成功
        """
        self.logger.info(f"开始数据迁移 {'(试运行模式)' if self.dry_run else '(实际执行)'}")
        
        try:
            # 1. 创建备份
            if create_backup:
                if not self.create_backup():
                    return False
            
            # 2. 确保目标目录存在
            self._ensure_directories()
            
            # 3. 构建URL映射
            self.url_directory_mapping = self._build_url_mapping()
            
            # 4. 迁移订阅数据
            if not self.migrate_subscriptions():
                return False
            
            # 5. 迁移已知内容
            if not self.migrate_known_items():
                return False
            
            # 6. 迁移消息映射
            if not self.migrate_message_mappings():
                return False
            
            # 7. 验证迁移结果（仅在实际执行时）
            if not self.dry_run:
                if not self.verify_migration():
                    return False
            
            # 8. 输出统计信息
            self.print_statistics()
            
            self.logger.info("🎉 数据迁移完成！")
            return True
            
        except Exception as e:
            self.logger.error(f"迁移过程中发生错误: {e}", exc_info=True)
            return False
    
    def print_statistics(self):
        """打印迁移统计信息"""
        self.logger.info("=" * 50)
        self.logger.info("📊 迁移统计信息")
        self.logger.info("=" * 50)
        self.logger.info(f"订阅数据迁移: {self.stats['subscriptions_migrated']} 个")
        self.logger.info(f"已知内容迁移: {self.stats['known_items_migrated']} 个URL")
        self.logger.info(f"消息映射迁移: {self.stats['message_mappings_migrated']} 个")
        self.logger.info(f"创建目录数量: {self.stats['directories_created']} 个")
        self.logger.info(f"错误数量: {len(self.stats['errors'])} 个")
        
        if self.stats['errors']:
            self.logger.info("\n❌ 错误详情:")
            for error in self.stats['errors']:
                self.logger.info(f"  - {error}")
        
        self.logger.info("=" * 50)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Douyin到Douyin1数据迁移工具')
    parser.add_argument('--dry-run', action='store_true', 
                       help='试运行模式，不实际修改文件')
    parser.add_argument('--no-backup', action='store_true',
                       help='不创建备份')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='详细输出')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 创建迁移器
    migrator = DouyinMigrator(dry_run=args.dry_run)
    
    # 执行迁移
    success = migrator.run_migration(create_backup=not args.no_backup)
    
    if success:
        print("✅ 迁移完成！")
        if args.dry_run:
            print("💡 这是试运行模式，要实际执行请移除 --dry-run 参数")
    else:
        print("❌ 迁移失败！请检查日志文件")
        exit(1)


if __name__ == "__main__":
    main() 