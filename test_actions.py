# -*- coding: utf-8 -*-
"""
动作扩展功能测试脚本
用于验证新增的动作标签和智能匹配功能
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

# 导入服务器端函数
from server_brain import determine_action_tag, detect_personality

# ============================================================
# 测试用例
# ============================================================

test_cases = [
    # (文本内容, 性格模式, 预期动作标签)
    ("你好！很高兴见到你！", "friendly", "greeting"),
    ("是的，没错，这样做是对的", "professional", "confirm"),
    ("太好了！真是太棒了！！", "enthusiastic", "excited"),
    ("让我想想这个问题...", "calm", "thinking"),
    ("让我解释一下这个概念", "professional", "explain"),
    ("看这里，这个很重要", "friendly", "pointing"),
    ("不是的，这样不对", "calm", "refuse"),
    ("哈哈，开心！😄", "humorous", "joy"),
    ("抱歉，我不太明白", "friendly", "sad"),
    ("为什么会这样呢？真的吗？", "curious", "curious"),
]

def test_action_detection():
    """测试动作标签检测功能"""
    print("=" * 70)
    print("动作标签智能检测测试")
    print("=" * 70)
    
    success_count = 0
    total_count = len(test_cases)
    
    for i, (text, personality, expected_action) in enumerate(test_cases, 1):
        detected_action = determine_action_tag(text, personality)
        is_correct = detected_action == expected_action
        
        status = "✅ PASS" if is_correct else "❌ FAIL"
        
        print(f"\n测试 {i}/{total_count}: {status}")
        print(f"  输入文本: {text}")
        print(f"  性格模式: {personality}")
        print(f"  预期动作: {expected_action}")
        print(f"  实际动作: {detected_action}")
        
        if is_correct:
            success_count += 1
    
    print("\n" + "=" * 70)
    print(f"测试结果: {success_count}/{total_count} 通过 ({success_count*100//total_count}%)")
    print("=" * 70)


def test_personality_detection():
    """测试性格检测功能"""
    print("\n" + "=" * 70)
    print("性格模式检测测试")
    print("=" * 70)
    
    personality_cases = [
        ("哈哈哈，太搞笑了😂", "humorous"),
        ("请问您能帮我分析一下这个数据吗？", "professional"),
        ("太棒了！！这真是太amazing了！", "enthusiastic"),
        ("我认为我们需要仔细考虑这个问题", "calm"),
        ("你好啊！", "friendly"),
    ]
    
    for text, expected in personality_cases:
        detected = detect_personality(text)
        status = "✅" if detected == expected else "❌"
        print(f"\n{status} 文本: {text}")
        print(f"   预期: {expected} | 实际: {detected}")


def show_available_actions():
    """显示所有可用的动作标签"""
    print("\n" + "=" * 70)
    print("可用动作标签列表")
    print("=" * 70)
    
    actions = [
        ("joy/happy", "快乐/高兴", "Happy_4", "开心、太好了、happy"),
        ("greeting/wave", "打招呼/挥手", "Hey_1", "你好、hello、hi"),
        ("confirm/yes/nodding", "确认/点头", "Yes_1", "是的、对的、没错"),
        ("refuse/no/shaking", "拒绝/摇头", "No_3", "不是、不对、no"),
        ("thinking", "思考", "Think_1", "想想、思考、考虑"),
        ("explain", "解释说明", "Explain_1", "解释、说明、举例"),
        ("pointing/show", "指向/展示", "You_1", "这个、那个、看"),
        ("excited", "兴奋激动", "Enthusiastic_4", "太棒了、amazing"),
        ("sad", "悲伤", "低头动作", "难过、抱歉、sorry"),
        ("curious/question", "好奇疑问", "IDontKnow_1", "为什么、怎么"),
    ]
    
    print(f"\n{'动作标签':<25} {'描述':<15} {'NAO动画':<20} {'关键词示例'}")
    print("-" * 70)
    
    for action, desc, animation, keywords in actions:
        print(f"{action:<25} {desc:<15} {animation:<20} {keywords}")
    
    print("\n总计: {} 种动作标签".format(len(actions)))


# ============================================================
# 主程序
# ============================================================

if __name__ == "__main__":
    print("\n🤖 NAO机器人动作扩展功能测试\n")
    
    # 1. 测试动作检测
    test_action_detection()
    
    # 2. 测试性格检测
    test_personality_detection()
    
    # 3. 显示可用动作
    show_available_actions()
    
    print("\n✅ 测试完成！\n")
