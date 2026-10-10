#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试客户端 - 用于测试服务器功能
可以模拟发送文本和图像数据到服务器
"""

import socket
import json
import base64
import time

# ============================================================
# 配置
# ============================================================
SERVER_IP = "127.0.0.1"  # 本地测试
SERVER_PORT = 9999

# ============================================================
# 测试函数
# ============================================================
def send_test_request(text, image_data=None):
    """
    向服务器发送测试请求
    
    参数：
        text (str): 测试文本
        image_data (str): Base64编码的图像（可选）
    
    返回：
        dict: 服务器响应
    """
    try:
        # 创建socket连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        
        print(f"\n{'='*60}")
        print(f"[测试] 发送请求: {text}")
        if image_data:
            print(f"[测试] 包含图像数据")
        
        sock.connect((SERVER_IP, SERVER_PORT))
        
        # 准备请求
        request = {"text": text}
        if image_data:
            request["image_data"] = image_data
        
        # 发送请求
        request_json = json.dumps(request, ensure_ascii=False) + '\n'
        sock.sendall(request_json.encode('utf-8'))
        
        # 接收响应
        response_data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
            if b'\n' in chunk:
                break
        
        # 解析响应
        response = json.loads(response_data.decode('utf-8'))
        
        print(f"[响应文本] {response['response_text']}")
        print(f"[动作标签] {response['action_tag']}")
        print(f"[性格模式] {response.get('personality', 'unknown')}")
        print(f"{'='*60}")
        
        sock.close()
        return response
        
    except Exception as e:
        print(f"[错误] 请求失败: {e}")
        return None


def create_mock_image():
    """
    创建一个模拟的图像数据（用于测试视觉功能）
    
    返回：
        str: Base64编码的模拟图像
    """
    # 创建一个简单的模拟图像数据
    mock_image_bytes = b"MOCK_IMAGE_DATA_FOR_TESTING" * 100
    return base64.b64encode(mock_image_bytes).decode('utf-8')


# ============================================================
# 测试场景
# ============================================================
def run_tests():
    """
    运行各种测试场景
    """
    print("=" * 60)
    print("NAO机器人服务器测试客户端")
    print("=" * 60)
    
    # 等待一秒确保服务器已启动
    time.sleep(1)
    
    # 测试1: 友好问候
    print("\n【测试1】友好问候")
    send_test_request("你好！今天天气真好啊")
    time.sleep(1)
    
    # 测试2: 幽默风格（触发性格切换）
    print("\n【测试2】幽默风格")
    send_test_request("哈哈哈！这也太好玩了吧😂")
    time.sleep(1)
    
    # 测试3: 专业风格
    print("\n【测试3】专业风格")
    send_test_request("请问您能否帮我分析一下这个数据的趋势？")
    time.sleep(1)
    
    # 测试4: 热情风格
    print("\n【测试4】热情风格")
    send_test_request("哇！这个太棒了！！真的太酷了！")
    time.sleep(1)
    
    # 测试5: 沉稳风格
    print("\n【测试5】沉稳风格")
    send_test_request("我认为我们需要仔细考虑一下这个问题，请解释为什么会出现这种情况")
    time.sleep(1)
    
    # 测试6: 视觉功能（带图像）
    print("\n【测试6】视觉功能 - 识别物体")
    mock_image = create_mock_image()
    send_test_request("这是什么东西？能告诉我吗？", mock_image)
    time.sleep(1)
    
    # 测试7: 再次切换到幽默模式
    print("\n【测试7】再次切换到幽默模式")
    send_test_request("哈哈，搞笑吧！")
    time.sleep(1)
    
    # 测试8: 普通问题
    print("\n【测试8】普通问题")
    send_test_request("你能帮我做什么？")
    time.sleep(1)
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


# ============================================================
# 交互式测试模式
# ============================================================
def interactive_mode():
    """
    交互式测试模式 - 可以手动输入测试文本
    """
    print("=" * 60)
    print("交互式测试模式")
    print("输入 'image' 来测试视觉功能")
    print("输入 'quit' 退出")
    print("=" * 60)
    
    while True:
        try:
            user_input = input("\n请输入测试文本: ")
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("退出测试")
                break
            
            if user_input.lower() == 'image':
                image_text = input("请输入图像相关的问题: ")
                mock_image = create_mock_image()
                send_test_request(image_text, mock_image)
            else:
                send_test_request(user_input)
                
        except KeyboardInterrupt:
            print("\n退出测试")
            break
        except Exception as e:
            print(f"错误: {e}")


# ============================================================
# 主程序
# ============================================================
if __name__ == "__main__":
    import sys
    
    print("\n请选择测试模式：")
    print("1. 自动测试（运行所有测试场景）")
    print("2. 交互式测试（手动输入）")
    
    choice = input("\n请输入选择 (1/2): ").strip()
    
    if choice == "1":
        run_tests()
    elif choice == "2":
        interactive_mode()
    else:
        print("自动运行测试...")
        run_tests()
