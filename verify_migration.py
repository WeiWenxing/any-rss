#!/usr/bin/env python3
"""
迁移结果验证脚本

用于快速验证douyin到douyin1的迁移结果
"""

import json
import sys
from pathlib import Path
from typing import Dict, List


def load_json_file(file_path: Path) -> Dict:
    """加载JSON文件"""
    try:
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"❌ 读取文件失败: {file_path}, 错误: {e}")
        return {}


def verify_subscriptions() -> bool:
    """验证订阅数据"""
    print("🔍 验证订阅数据...")
    
    source_file = Path("storage/douyin/config/subscriptions.json")
    target_file = Path("storage/douyin1/config/subscriptions.json")
    
    if not source_file.exists():
        print("⚠️  源订阅文件不存在，跳过验证")
        return True
    
    if not target_file.exists():
        print("❌ 目标订阅文件不存在")
        return False
    
    source_data = load_json_file(source_file)
    target_data = load_json_file(target_file)
    
    if source_data == target_data:
        print(f"✅ 订阅数据验证通过 ({len(source_data)} 个订阅)")
        return True
    else:
        print("❌ 订阅数据不匹配")
        print(f"源数据: {len(source_data)} 个订阅")
        print(f"目标数据: {len(target_data)} 个订阅")
        return False


def verify_message_mappings() -> bool:
    """验证消息映射"""
    print("🔍 验证消息映射...")
    
    source_file = Path("storage/douyin/config/message_mappings.json")
    target_file = Path("storage/douyin1/config/message_mappings.json")
    
    if not source_file.exists():
        print("⚠️  源消息映射文件不存在，跳过验证")
        return True
    
    if not target_file.exists():
        print("❌ 目标消息映射文件不存在")
        return False
    
    source_data = load_json_file(source_file)
    target_data = load_json_file(target_file)
    
    if source_data == target_data:
        print(f"✅ 消息映射验证通过 ({len(source_data)} 个映射)")
        return True
    else:
        print("❌ 消息映射不匹配")
        return False


def verify_known_items() -> bool:
    """验证已知内容"""
    print("🔍 验证已知内容...")
    
    source_data_dir = Path("storage/douyin/data")
    target_data_dir = Path("storage/douyin1/data")
    
    if not source_data_dir.exists():
        print("⚠️  源数据目录不存在，跳过验证")
        return True
    
    if not target_data_dir.exists():
        print("❌ 目标数据目录不存在")
        return False
    
    # 统计数量
    source_count = 0
    target_count = 0
    
    # 检查源目录
    for hash_dir in source_data_dir.iterdir():
        if hash_dir.is_dir():
            known_items_file = hash_dir / "known_item_ids.json"
            if known_items_file.exists():
                source_count += 1
    
    # 检查目标目录
    for safe_dir in target_data_dir.iterdir():
        if safe_dir.is_dir():
            known_items_file = safe_dir / "known_item_ids.json"
            if known_items_file.exists():
                target_count += 1
    
    print(f"📊 源目录已知内容文件: {source_count} 个")
    print(f"📊 目标目录已知内容文件: {target_count} 个")
    
    if source_count == target_count:
        print("✅ 已知内容数量验证通过")
        return True
    else:
        print("❌ 已知内容数量不匹配")
        return False


def check_directory_structure() -> bool:
    """检查目录结构"""
    print("🔍 检查目录结构...")
    
    required_dirs = [
        "storage/douyin1",
        "storage/douyin1/config",
        "storage/douyin1/data",
        "storage/douyin1/media"
    ]
    
    all_exist = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"✅ {dir_path}")
        else:
            print(f"❌ {dir_path} (不存在)")
            all_exist = False
    
    return all_exist


def print_summary():
    """打印总结信息"""
    print("\n" + "="*50)
    print("📋 迁移验证总结")
    print("="*50)
    
    # 检查文件大小
    files_to_check = [
        "storage/douyin1/config/subscriptions.json",
        "storage/douyin1/config/message_mappings.json"
    ]
    
    for file_path in files_to_check:
        path = Path(file_path)
        if path.exists():
            size = path.stat().st_size
            print(f"📄 {file_path}: {size} 字节")
        else:
            print(f"❌ {file_path}: 文件不存在")
    
    # 统计数据目录
    data_dir = Path("storage/douyin1/data")
    if data_dir.exists():
        subdirs = [d for d in data_dir.iterdir() if d.is_dir()]
        print(f"📁 数据目录: {len(subdirs)} 个子目录")
    
    print("="*50)


def main():
    """主函数"""
    print("🔍 开始验证迁移结果...\n")
    
    all_passed = True
    
    # 检查目录结构
    if not check_directory_structure():
        all_passed = False
    
    print()
    
    # 验证订阅数据
    if not verify_subscriptions():
        all_passed = False
    
    print()
    
    # 验证消息映射
    if not verify_message_mappings():
        all_passed = False
    
    print()
    
    # 验证已知内容
    if not verify_known_items():
        all_passed = False
    
    print()
    
    # 打印总结
    print_summary()
    
    # 最终结果
    if all_passed:
        print("\n🎉 验证通过！迁移成功完成。")
        return 0
    else:
        print("\n❌ 验证失败！请检查迁移过程。")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 