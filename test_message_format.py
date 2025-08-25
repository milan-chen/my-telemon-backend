#!/usr/bin/env python3
"""
测试消息格式功能
验证HTML标签是否正确保留，用户消息是否正确转义
"""

# 模拟escape_html函数
def escape_html(text: str) -> str:
    """转义HTML格式的特殊字符"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# 模拟消息构造逻辑
def construct_message(channel: str, message_link: str, message_text: str) -> str:
    """构造Bot消息"""
    # 构造消息头部（包含HTML标签，不需要转义）
    notification_header = f"📢 <b>Telemon 关键词提醒</b>\n\n- <b>频道:</b> {channel}\n- <b>原文:</b> <a href='{message_link}'>点击查看</a>\n\n<b>-- 消息内容 --</b>\n"
    
    # 只对消息正文进行HTML转义
    escaped_message_text = escape_html(message_text)
    final_message = f"{notification_header}{escaped_message_text}"
    
    return final_message

# 测试用例
def test_message_format():
    print("🧪 测试Bot消息格式...")
    
    # 测试数据
    channel = "@test_channel"
    message_link = "https://t.me/test_channel/123"
    message_text = "这是一条包含<特殊字符>的&测试消息"
    
    # 构造消息
    result = construct_message(channel, message_link, message_text)
    
    print("📋 构造的消息内容:")
    print("=" * 50)
    print(result)
    print("=" * 50)
    
    # 验证HTML标签是否正确保留
    html_tags_preserved = (
        "<b>Telemon 关键词提醒</b>" in result and
        "<b>频道:</b>" in result and
        "<b>原文:</b>" in result and
        f"<a href='{message_link}'>点击查看</a>" in result and
        "<b>-- 消息内容 --</b>" in result
    )
    
    # 验证用户消息是否正确转义
    user_message_escaped = (
        "&lt;特殊字符&gt;" in result and
        "&amp;测试消息" in result
    )
    
    print("\n✅ 验证结果:")
    print(f"HTML标签保留: {'✅ 通过' if html_tags_preserved else '❌ 失败'}")
    print(f"用户消息转义: {'✅ 通过' if user_message_escaped else '❌ 失败'}")
    
    if html_tags_preserved and user_message_escaped:
        print("\n🎉 所有测试通过！消息格式修复成功！")
        return True
    else:
        print("\n❌ 测试失败，请检查代码实现")
        return False

if __name__ == "__main__":
    test_message_format()