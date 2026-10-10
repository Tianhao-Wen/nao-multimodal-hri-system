#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉功能测试 - 测试图像识别
"""

import socket
import json
import base64

SERVER_IP = "127.0.0.1"
SERVER_PORT = 9999

def send_vision_request(text, image_path=None):
    """发送带图像的请求"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((SERVER_IP, SERVER_PORT))
        
        request = {"text": text}
        
        # 如果提供了图像路径，读取并编码
        if image_path:
            try:
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                request["image_data"] = image_data
                print(f"✓ 已加载图像: {image_path}")
            except Exception as e:
                print(f"✗ 无法加载图像: {e}")
                # 使用模拟图像数据
                mock_image = b"MOCK_IMAGE_DATA" * 100
                request["image_data"] = base64.b64encode(mock_image).decode('utf-8')
                print("✓ 使用模拟图像数据")
        
        print(f"\n{'='*60}")
        print(f"发送问题: {text}")
        print(f"{'='*60}")
        
        # 发送请求
        sock.sendall((json.dumps(request, ensure_ascii=False) + '\n').encode('utf-8'))
        
        # 接收响应
        response_data = b''
        while True:
            chunk = sock.recv(4096)
            if not chunk or b'\n' in chunk:
                response_data += chunk
                break
            response_data += chunk
        
        response = json.loads(response_data.decode('utf-8'))
        
        print(f"\n🤖 机器人回复:")
        print(f"{response['response_text']}")
        print(f"\n📋 详情:")
        print(f"  - 动作: {response['action_tag']}")
        print(f"  - 性格: {response.get('personality', 'unknown')}")
        print(f"{'='*60}\n")
        
        sock.close()
        return response
        
    except Exception as e:
        print(f"✗ 错误: {e}")
        return None


print("="*60)
print("NAO机器人视觉功能测试")
print("="*60)

# 测试: 使用真实图片 1.jpg
print("\n【测试】识别图片内容 - 1.jpg")
send_vision_request("你看看这是什么？请详细描述一下这张图片。", "2.jpg")

print("\n✅ 测试完成！")
