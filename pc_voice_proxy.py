# -*- coding: utf-8 -*-
"""
电脑语音代理 - 替代NAO语音识别
处理电脑端语音输入，自动发送给NAO执行
"""

import socket
import json
import speech_recognition as sr
import time
import pyaudio    # 新增：用于底层录音
import keyboard   # 新增：用于监听键盘长按

# ============================================================
# 配置参数
# ============================================================
LOCAL_TEST_MODE = False  # True=本地测试模式（不需要NAO），False=正常模式（需要NAO）

SERVER_IP = "192.168.172.1"  # 服务器IP（运行server_brain.py的电脑，通常是本机）
SERVER_PORT = 9999
NAO_IP = "169.254.215.197"  # NAO的IP（从NAO胸前按钮获取）
NAO_PORT = 9998  # NAO监听指令的端口

# 视觉触发关键词
VISION_KEYWORDS = [
    "look", "see", "watch", "show", "check", "observe", "view", 
    "recognize", "identify", "what's this", "what is this", 
    "what's that", "what is that", "can you see", "what do you see",
    "describe this", "take a look", "photo", "picture", "image"
]

# ============================================================
# 语音识别功能 (已修改为：长按空格录音，松开识别)
# ============================================================
def record_and_recognize():
    """
    录音并识别语音（英文）- 对讲机长按模式
    
    返回：
        str: 识别的文本
    """
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"❌ [麦克风错误] 无法打开麦克风: {e}")
        return None

    print("\n🎤 [录音准备] 请【长按 空格键(Space)】开始说话...")

    # 等待用户按下空格键
    while not keyboard.is_pressed('space'):
        time.sleep(0.05)

    print("🔴 [录音中...] 保持按住空格键，说话中... (松开立即结束)")

    frames = []
    # 只要空格键处于按下状态，就一直录音
    while keyboard.is_pressed('space'):
        try:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
        except Exception:
            break

    print("✅ [录音结束] 松开按键，正在处理音频...")

    # 停止底层音频流
    stream.stop_stream()
    stream.close()
    p.terminate()

    # 将音频数据打包给 speech_recognition 库去识别
    audio_data = b''.join(frames)
    sample_width = p.get_sample_size(FORMAT)
    audio = sr.AudioData(audio_data, RATE, sample_width)

    recognizer = sr.Recognizer()
    print("🔄 [识别] 正在请求Google识别语音...")
    
    try:
        text = recognizer.recognize_google(audio, language="en-US")
        print(f"✅ [识别成功] {text}")
        return text
    except sr.UnknownValueError:
        print("❌ [识别失败] 无法理解音频")
        return None
    except sr.RequestError as e:
        print(f"❌ [识别错误] Google API错误: {e}")
        return None
    except Exception as e:
        print(f"❌ [错误] {e}")
        return None


def send_command_to_nao(text, needs_vision=False):
    """
    发送指令给NAO执行
    
    参数：
        text (str): 要发送的文本
        needs_vision (bool): 是否需要视觉功能
    
    返回：
        bool: 是否发送成功
    """
    # 本地测试模式：只打印，不发送
    if LOCAL_TEST_MODE:
        print(f"\n[本地测试] 模拟发送指令：")
        print(f"  文本: {text}")
        print(f"  需要视觉: {'是' if needs_vision else '否'}")
        print(f"  [提示] 这只是模拟，没有真正发送到NAO")
        print(f"  [提示] 设置 LOCAL_TEST_MODE=False 可切换到真实NAO模式")
        return True
    
    # 正常模式：发送到NAO
    try:
        # 连接到NAO
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        
        print(f"[PROXY] 正在连接NAO {NAO_IP}:{NAO_PORT}...")
        sock.connect((NAO_IP, NAO_PORT))
        
        # 准备指令
        command = {
            "text": text,
            "needs_vision": needs_vision,
            "from_pc": True  # 标记来自电脑
        }
        
        # 发送指令
        command_json = json.dumps(command, ensure_ascii=False) + '\n'
        sock.sendall(command_json.encode('utf-8'))
        print(f"[PROXY] ✅ 已发送指令到NAO")
        
        sock.close()
        return True
        
    except Exception as e:
        print(f"[PROXY] ❌ 发送失败: {e}")
        return False


# ============================================================
# 主循环
# ============================================================
def main():
    """
    电脑语音代理主循环
    """
    import sys
    
    # 强制刷新输出
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.write("🎙️  电脑语音代理 - NAO语音识别助手\n")
    sys.stdout.write("=" * 60 + "\n")
    sys.stdout.flush()
    
    print("=" * 60)
    print("🎙️  电脑语音代理 - NAO语音识别助手")
    print("=" * 60)
    
    if LOCAL_TEST_MODE:
        print("🧪 [模式] 本地测试模式（不需要NAO）")
        print("")
        print("功能：")
        print("  • 电脑麦克风录音")
        print("  • Google语音识别（英文，~95%准确率）")
        print("  • 视觉关键词检测")
        print("  • 模拟NAO指令发送")
        print("")
        print("💡 切换到真实NAO模式：修改代码 LOCAL_TEST_MODE=False")
    else:
        print("🤖 [模式] 真实NAO模式")
        print(f"服务器: {SERVER_IP}:{SERVER_PORT}")
        print(f"NAO机器人: {NAO_IP}:{NAO_PORT}")
        print("")
        print("功能：")
        print("  • 电脑麦克风录音 + Google语音识别（英文）")
        print("  • 自动检测视觉需求")
        print("  • 发送指令给NAO执行")
    
    print("")
    print("操作：按Enter录音，输入文本直接发送，输入 'quit' 退出")
    print("=" * 60)
    
    while True:
        try:
            # 提示用户
            user_input = input("\n💬 [输入] 按Enter录音，或输入文本：").strip()
            
            # 退出
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 再见！")
                break
            
            # 判断输入方式
            if not user_input:
                # 录音模式
                text = record_and_recognize()
                if not text:
                    continue
            else:
                # 键盘模式
                text = user_input
            
            # 检查是否需要视觉
            needs_vision = any(keyword in text.lower() for keyword in VISION_KEYWORDS)
            
            print(f"\n📝 [文本] {text}")
            if needs_vision:
                print("📸 [视觉] 检测到视觉关键词，NAO将拍照")
            else:
                print("📸 [视觉] 无需视觉")
            
            # 发送给NAO
            success = send_command_to_nao(text, needs_vision)
            
            if success:
                if LOCAL_TEST_MODE:
                    print("✅ [完成] 本地测试完成")
                else:
                    print("✅ [完成] 指令已发送，NAO正在处理...")
            else:
                print("❌ [失败] 无法连接到NAO")
                print("💡 [提示] 请确保：")
                print("   1. NAO已启动并运行 robot_client.py")
                print("   2. NAO IP地址正确")
                print("   3. NAO防火墙允许端口9998")
            
        except KeyboardInterrupt:
            print("\n👋 用户中断，退出")
            break
        except Exception as e:
            print(f"❌ [错误] {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    import sys
    print("=" * 60, file=sys.stderr)
    print("[DEBUG] Starting pc_voice_proxy.py...", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    sys.stderr.flush()
    
    try:
        main()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)