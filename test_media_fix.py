#!/usr/bin/env python3
"""
测试MediaInfo修复效果
"""

def test_media_info():
    """测试MediaInfo对象是否正常工作"""
    try:
        from services.common.media_strategy import MediaInfo
        
        # 创建MediaInfo对象
        media = MediaInfo('test.jpg', 'image')
        
        print("✅ MediaInfo对象创建成功")
        print(f"   url: {media.url}")
        print(f"   media_type: {media.media_type}")
        print(f"   poster_url: {media.poster_url}")
        print(f"   local_path: {media.local_path}")
        
        # 检查是否还有send_strategy属性
        if hasattr(media, 'send_strategy'):
            print("❌ 错误：send_strategy属性仍然存在")
            return False
        else:
            print("✅ 修复成功：send_strategy属性已被正确移除")
            return True
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False

def test_unified_sender_import():
    """测试unified_sender是否能正常导入"""
    try:
        from services.common.unified_sender import UnifiedTelegramSender
        print("✅ UnifiedTelegramSender导入成功")
        return True
    except Exception as e:
        print(f"❌ UnifiedTelegramSender导入失败: {str(e)}")
        return False

if __name__ == "__main__":
    print("🧪 开始测试MediaInfo修复效果...")
    print()
    
    success1 = test_media_info()
    print()
    
    success2 = test_unified_sender_import()
    print()
    
    if success1 and success2:
        print("🎉 所有测试通过！修复成功！")
    else:
        print("❌ 部分测试失败，需要进一步检查") 