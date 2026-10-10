# -*- coding: utf-8 -*-
"""
机器人客户端 - NAO机器人端（兼容Python 2.7）
处理机器人的音频/视觉/运动功能
通信方式：TCP Socket 客户端连接到笔记本服务器
"""

from __future__ import print_function
import socket
import json
import sys
import time
import base64
import threading  # 用于并行执行动作和TTS

# ============================================================
# 配置参数
# ============================================================
# SERVER_IP = "127.0.0.1"  # 本地测试使用localhost（在同一台电脑上测试时）
SERVER_IP = "169.254.4.229"  # 电脑的IP地址（NAO需要连接到运行server_brain.py的电脑）
SERVER_PORT = 9999

# 实验条件开关（每次换参与者时修改）
# "vision"    = 实验组 Condition B：听到look/see时拍照并分析
# "no_vision" = 对照组 Condition A：听到look/see时说“我看不见”，不拍照
EXPERIMENT_CONDITION = "vision"  # 改为 "no_vision" 即切换对照组

# 电脑代理配置（电脑替代NAO语音识别）
ENABLE_PC_PROXY = True  # 启用电脑语音代理模式
PC_PROXY_PORT = 9998  # 监听电脑指令的端口

TEST_MODE = False  # 在真实NAO机器人上运行时设置为False

# 语音识别配置
USE_SPEECH_RECOGNITION = False  # 使用录音+Qwen-Audio代替NAO本地识别
USE_AUDIO_RECORDING = False  # 启用录音功能传给服务器
RECORDING_DURATION = 5  # 录音时长（秒）
SPEECH_LANGUAGE = "English"  # 语音识别语言：Chinese 或 English
USE_VOCABULARY = False  # 是否使用自定义词汇表（NAOqi可能不支持，设为False跳过）

# 语音识别词汇表（常用词汇，提高识别率）
VOCABULARY = [
    u"hello", u"goodbye", u"thanks", u"help",
    u"look", u"see", u"what", u"this", u"that",
    u"happy", u"sad", u"good", u"bad"
]

# 视觉触发关键词（支持中英文）
VISION_KEYWORDS = [
    # ========== 英文关键词 ==========
    # 基础动词
    "look", "see", "watch", "show", "check", "observe", "view", "recognize", "identify",
    
    # 询问类
    "what's this", "what is this", "what's that", "what is that",
    "who's this", "who is this", "who's that", "who is that",
    "can you see",
    
    # 物体/场景
    "what do you see", "tell me what you see", "describe this", "describe that",
    "what's in front of you", "what are you looking at",
    
    # 动作短语
    "take a look", "have a look", "let me show you", "look at this", "look at that",
    
    # 图片相关
    "photo", "picture", "image", "take a photo", "capture",
    
    # ========== 中文关键词 ==========
    # 基础动词
    u"看", u"瞧", u"瞅", u"观察", u"检查", u"识别", u"认出",
    
    # 询问类 - 物体
    u"这是什么", u"那是什么", u"是什么", u"什么东西", u"这个是啥", u"那个是啥",
    u"这是啥", u"那是啥", u"啥东西", u"这什么", u"那什么",
    
    # 指示类
    u"看这个", u"看那个", u"看一下", u"看看", u"瞧瞧", u"瞅瞅",
    u"让我看", u"给我看", u"你看", u"你瞧", u"帮我看看",
    
    # 场景描述
    u"你看到了什么", u"你看见什么", u"看见什么了", u"看到什么",
    u"你前面是什么", u"面前是什么", u"眼前是什么",
    
    # 动作指令
    u"拍照", u"拍个照", u"照片", u"图片", u"拍张照片"
]


# ============================================================
# 模拟代理（用于在没有真实机器人时测试）
# ============================================================
class MockProxy(object):
    """
    NAOqi ALProxy的模拟实现，用于在PC上测试
    通过打印语句模拟机器人动作
    """
    def __init__(self, service_name, ip, port):
        self.service_name = service_name
        print("[MOCK] 已初始化 {} (测试模式)".format(service_name))
    
    # ALTextToSpeech 模拟
    def say(self, text):
        print("[MOCK TTS] 机器人说：\"{}\"".format(text))
        time.sleep(1)  # 模拟说话时长
    
    def setLanguage(self, language):
        print("[MOCK TTS] 语言设置为：{}".format(language))
    
    # ALRobotPosture 模拟
    def goToPosture(self, posture, speed):
        print("[MOCK POSTURE] 移动到姿态：{} (速度：{})".format(posture, speed))
        time.sleep(1)
    
    # ALMotion 模拟（用于动画）
    def setAngles(self, joint, angle, speed):
        print("[MOCK MOTION] 设置 {} 到 {} 度 (速度：{})".format(joint, angle, speed))
    
    def angleInterpolation(self, names, angles, times, isAbsolute):
        print("[MOCK MOTION] 运行动画：{} 个关节".format(len(names)))
        time.sleep(2)
    
    # ALVideoDevice 模拟
    def subscribeCamera(self, name, camera_id, resolution, colorspace, fps):
        print("[MOCK CAMERA] 已订阅摄像头 {} (分辨率：{})".format(camera_id, resolution))
        return "mock_camera_handle"
    
    def getImageRemote(self, handle):
        print("[MOCK CAMERA] 正在捕获图像...")
        # 返回模拟图像数据结构
        # 真实格式：[width, height, layers, colorspace, timestamp, binary_data]
        mock_image_data = [320, 240, 3, 11, int(time.time()), "mock_binary_data"]
        return mock_image_data
    
    def unsubscribe(self, handle):
        print("[MOCK CAMERA] 已取消订阅摄像头")
    
    # ALSpeechRecognition 模拟
    def setLanguage(self, language):
        print("[MOCK SPEECH] 语音识别语言设置为：{}".format(language))
    
    def setVocabulary(self, vocabulary, enable):
        print("[MOCK SPEECH] 设置词汇表：{} 个词".format(len(vocabulary)))
    
    def subscribe(self, name):
        print("[MOCK SPEECH] 订阅语音识别：{}".format(name))
    
    def unsubscribe(self, name):
        print("[MOCK SPEECH] 取消订阅语音识别：{}".format(name))
    
    # ALMemory 模拟
    def getData(self, key):
        # 模拟返回语音识别结果
        if "WordRecognized" in key:
            return ["你好", 0.8]  # [识别的词, 置信度]
        return None
    
    def subscribeToEvent(self, event_name, module_name, callback_name):
        print("[MOCK MEMORY] 订阅事件：{}".format(event_name))


# ============================================================
# 硬件抽象层
# ============================================================
def init_robot_services():
    """
    初始化NAOqi服务（或在TEST_MODE下使用模拟服务）
    
    返回：
        dict: 机器人服务代理的字典
    """
    if TEST_MODE:
        print("[INIT] 运行在测试模式（模拟代理）")
        ProxyClass = MockProxy
        robot_ip = "127.0.0.1"
        robot_port = 9559
    else:
        print("[INIT] 运行在真实NAO机器人上")
        try:
            from naoqi import ALProxy
            ProxyClass = ALProxy
            robot_ip = "127.0.0.1"  # 在机器人上运行时的本地IP
            robot_port = 9559
        except ImportError:
            print("[ERROR] 未找到NAOqi SDK！请安装NAOqi或启用TEST_MODE。")
            sys.exit(1)
    
    # 初始化服务
    print("[INIT] 正在初始化NAOqi服务...")
    sys.stdout.flush()
    
    services = {
        'tts': ProxyClass("ALTextToSpeech", robot_ip, robot_port),
        'posture': ProxyClass("ALRobotPosture", robot_ip, robot_port),
        'video': ProxyClass("ALVideoDevice", robot_ip, robot_port),
        'motion': ProxyClass("ALMotion", robot_ip, robot_port),
        'animation': ProxyClass("ALAnimationPlayer", robot_ip, robot_port),
        'speech': ProxyClass("ALSpeechRecognition", robot_ip, robot_port),
        'memory': ProxyClass("ALMemory", robot_ip, robot_port),
        'audio': ProxyClass("ALAudioDevice", robot_ip, robot_port)  # 音频设备服务
    }
    
    print("[INIT] ✓ 所有服务已连接")
    sys.stdout.flush()
    
    # 设置默认语言（英语）
    try:
        services['tts'].setLanguage("English")
        print("[INIT] TTS语言设置为：English")
        sys.stdout.flush()
    except Exception as e:
        print("[ERROR] TTS语言设置失败：{}".format(e))
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
    
    # 设置音量（确保NAO能发出声音）
    try:
        current_volume = services['tts'].getVolume()
        print("[INIT] 当前TTS音量：{}".format(current_volume))
        sys.stdout.flush()
        if current_volume < 0.5:
            services['tts'].setVolume(0.8)
            print("[INIT] TTS音量已设置为：0.8")
            sys.stdout.flush()
    except Exception as e:
        print("[WARNING] 无法设置音量：{}".format(e))
        sys.stdout.flush()
    
    # 配置语音识别
    if USE_SPEECH_RECOGNITION and not TEST_MODE:
        try:
            print("[INIT] 正在配置语音识别...")
            services['speech'].setLanguage(SPEECH_LANGUAGE)
            
            # 只在启用词汇表时设置（默认禁用，因为NAOqi可能不支持）
            if USE_VOCABULARY:
                services['speech'].setVocabulary(VOCABULARY, True)
                print("[INIT] 词汇表已设置")
            
            print("[INIT] 语音识别已配置")
        except Exception as e:
            print("[ERROR] 语音识别配置失败：{}".format(e))
            print("[INFO] 继续运行，但词汇表功能可能不可用")
    
    return services


# ============================================================
# 语音识别（真实语音输入）
# ============================================================
def listen_for_speech(services, timeout=10):
    """
    启动语音识别并等待用户说话
    
    参数：
        services (dict): 机器人服务代理
        timeout (int): 超时时间（秒）
    
    返回：
        str: 识别到的文本，失败返回None
    """
    if TEST_MODE or not USE_SPEECH_RECOGNITION:
        # 测试模式：使用键盘输入
        if sys.version_info[0] == 2:
            return raw_input("[输入] 请输入文本（或'quit'退出）：").decode('utf-8')
        else:
            return input("[输入] 请输入文本（或'quit'退出）：")
    
    speech = services['speech']
    memory = services['memory']
    
    try:
        print("[SPEECH] 正在听... 请说话")
        
        # 订阅语音识别
        speech.subscribe("RobotSpeechRecognition")
        
        # 等待语音输入
        start_time = time.time()
        recognized_text = None
        
        while time.time() - start_time < timeout:
            # 从内存中读取识别结果
            result = memory.getData("WordRecognized")
            
            if result and len(result) > 0:
                word = result[0]
                confidence = result[1]
                
                # 置信度阈值：只接受高置信度的识别结果
                if confidence > 0.4:  # 40%以上置信度
                    recognized_text = word
                    print(u"[SPEECH] 识别到：{} (置信度：{:.2f})".format(word, confidence))
                    break
            
            time.sleep(0.1)  # 短暂等待
        
        # 取消订阅
        speech.unsubscribe("RobotSpeechRecognition")
        
        if recognized_text:
            return recognized_text
        else:
            print("[SPEECH] 超时或未识别到语音")
            return None
            
    except Exception as e:
        print("[ERROR] 语音识别错误：{}".format(e))
        try:
            speech.unsubscribe("RobotSpeechRecognition")
        except:
            pass
        return None


# ============================================================
# 视觉捕获（按需触发）
# ============================================================
def capture_image(video_service):
    """
    从NAO的摄像头捕获图像并编码为base64
    
    参数：
        video_service: ALVideoDevice 代理
    
    返回：
        str: Base64编码的图像字符串（失败返回None）
    """
    try:
        # 订阅摄像头
        # 摄像头ID：0=顶部，1=底部 | 分辨率：2=640x480, 1=320x240, 0=160x120
        # 色彩空间：11=RGB
        # 使用320x240降低图像大小，避免传输超时
        camera_handle = video_service.subscribeCamera(
            "python_client", 0, 1, 11, 10
        )
        
        # 捕获图像
        image_data = video_service.getImageRemote(camera_handle)
        
        # 取消订阅
        video_service.unsubscribe(camera_handle)
        
        if TEST_MODE:
            # 测试模式：返回None表示没有真实图像
            # 服务器端会检测并给出适当的测试响应
            print("[VISION] ⚠️ 测试模式：无法捕获真实图像")
            print("[VISION] 💡 提示：在真实NAO机器人上运行时，将捕获实际摄像头图像")
            return None  # 返回None而不是模拟数据
        else:
            # 提取二进制数据并转换为JPEG格式
            width = image_data[0]
            height = image_data[1]
            binary_data = image_data[6]
            
            print("[VISION] 已捕获原始图像：{}x{}".format(width, height))
            
            # 将原始RGB数据转换为JPEG格式
            try:
                from PIL import Image
                # Python 2.7兼容：使用StringIO
                try:
                    from io import BytesIO
                except ImportError:
                    from StringIO import StringIO as BytesIO
                
                # 创建PIL Image对象（RGB格式）
                img = Image.frombytes("RGB", (width, height), binary_data)
                
                # 转换为JPEG并保存到字节流
                img_bytes = BytesIO()
                img.save(img_bytes, format='JPEG', quality=85)
                img_bytes.seek(0)
                
                # Base64编码JPEG数据
                jpeg_data = img_bytes.read()
                print("[VISION] 已转换为JPEG格式：{} 字节".format(len(jpeg_data)))
                return base64.b64encode(jpeg_data).decode('utf-8')
                
            except ImportError:
                print("[WARNING] PIL/Pillow未安装，尝试使用原始数据")
                # 如果没有PIL，直接返回原始数据（可能导致API错误）
                return base64.b64encode(binary_data).decode('utf-8')
            
    except Exception as e:
        print("[ERROR] 捕获图像失败：{}".format(e))
        return None


# ============================================================
# 音频录制（录音传服务器识别）
# ============================================================
def record_audio(services, duration=5):
    """
    从NAO的麦克风录制音频并编码为base64
    
    参数：
        services (dict): 机器人服务代理
        duration (int): 录音时长（秒）
    
    返回：
        str: Base64编码的音频字符串（WAV格式），失败返回None
    """
    if TEST_MODE:
        print("[AUDIO] ⚠️ 测试模式：无法录制真实音频")
        print("[AUDIO] 💡 提示：在真实NAO机器人上运行时，将录制实际麦克风音频")
        return None
    
    try:
        # NAO的音频设备服务
        audio = services.get('audio')
        if not audio:
            print("[ERROR] 音频服务未初始化")
            return None
        
        print("[AUDIO] 🎤 开始录音（{}秒）...".format(duration))
        
        # 配置录音参数
        # 采样率：16000Hz（NAO标准）
        # 声道：4（NAO有4个麦克风，通常使用前置麦克风）
        # 格式：16位PCM
        
        # 订阅音频流
        audio_module = "python_audio_recorder"
        
        # NAO录音方法1：使用ALAudioRecorder（推荐）
        try:
            from naoqi import ALProxy
            audio_recorder = ALProxy("ALAudioRecorder", "127.0.0.1", 9559)
            
            # 录音文件保存到NAO本地
            audio_file = "/tmp/nao_recording.wav"
            audio_recorder.startMicrophonesRecording(audio_file, "wav", 16000, (0, 0, 1, 0))  # 前置麦克风
            
            # 等待录音完成
            time.sleep(duration)
            
            # 停止录音
            audio_recorder.stopMicrophonesRecording()
            print("[AUDIO] ✅ 录音完成：{}".format(audio_file))
            
            # 读取音频文件并编码为base64
            with open(audio_file, 'rb') as f:
                audio_binary = f.read()
            
            print("[AUDIO] 音频大小：{} 字节".format(len(audio_binary)))
            return base64.b64encode(audio_binary).decode('utf-8')
            
        except Exception as e_recorder:
            print("[WARNING] ALAudioRecorder失败：{}，尝试备用方法".format(e_recorder))
            
            # 备用方法2：使用ALAudioDevice（较复杂，返回原始PCM数据）
            # 这里简化处理，返回None
            print("[ERROR] 无法录制音频，请检查NAO麦克风")
            return None
    
    except Exception as e:
        print("[ERROR] 录音失败：{}".format(e))
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# 文本清理（移除emoji和特殊字符）
# ============================================================
def clean_text_for_tts(text):
    """
    清理文本，移除NAOqi TTS无法处理的字符（emoji、特殊符号等）
    NAO的say()方法需要纯ASCII字符串
    
    参数：
        text (str/unicode): 原始文本
    
    返回：
        str: 清理后的ASCII字符串（Python 2.7兼容）
    """
    if not text:
        return ""
    
    try:
        # Python 2.7兼容：先转换为unicode
        if sys.version_info[0] == 2:
            if isinstance(text, str):
                text = text.decode('utf-8', 'ignore')
        
        # 最简单的方法：只删除明显的emoji表情符号
        # 保留所有其他字符（中文、英文、标点等）
        # 这样NAO TTS可以处理大部分文本
        
        # 删除常见emoji（使用简单的范围）
        # 笑脸、符号、图标等
        text = text.replace(u'😊', '').replace(u'🌟', '').replace(u'✅', '')
        text = text.replace(u'🔹', '').replace(u'💛', '').replace(u'🤖', '')
        text = text.replace(u'✨', '').replace(u'🌱', '').replace(u'📢', '')
        text = text.replace(u'📷', '').replace(u'🎤', '').replace(u'🔊', '')
        
        # 移除多余的空格
        text = ' '.join(text.split())
        
        # Python 2.7：转回UTF-8编码的str给NAO TTS
        if sys.version_info[0] == 2:
            if isinstance(text, unicode):
                text = text.encode('utf-8')
        
        # 确保返回非空字符串
        return text if text else "I received your message."
        
    except Exception as e:
        print("[ERROR] 文本清理失败：{}".format(e))
        import traceback
        traceback.print_exc()
        # 发生错误时返回安全的备用文本
        return "I received your message."


# ============================================================
# 动作执行（基于动作标签）
# ============================================================
def execute_action(action_tag, services):
    """
    根据动作标签执行机器人运动/动画
    支持使用NAO内置动画库(ALAnimationPlayer)提供更丰富可靠的动作
    
    参数：
        action_tag (str): 要执行的动作标签
        services (dict): 机器人服务代理
    
    动作标签列表：
        基础动作：
        - joy/happy: 快乐/高兴
        - greeting/wave: 打招呼/挥手
        - confirm/yes/nodding: 确认/点头
        - refuse/no/shaking: 拒绝/摇头
        - thinking: 思考
        - explain: 解释说明
        - pointing/show: 指向/展示
        - excited: 兴奋激动
        - sad: 悲伤
        - curious/question: 好奇疑问
        
        扩展动作：
        - applause/clap: 鼓掌
        - celebrate: 庆祝
        - bow: 鞠躬
        - goodbye/bye: 再见
        - cheer/encourage: 加油鼓励
        - sorry/apologize: 抱歉道歉
        - surprised/shocked: 惊讶震惊
        - shy/embarrassed: 害羞尴尬
        - laugh: 大笑
        - relax/calm: 放松冷静
        - dance: 跳舞
        - sleep/tired: 困倦
    """
    motion = services['motion']
    animation = services.get('animation')  # 动画播放器
    
    print("[ACTION] 执行动作：{}".format(action_tag))
    
    # 在真实模式下确保motion服务已启用
    if not TEST_MODE:
        try:
            motion.setStiffnesses("Body", 1.0)
            time.sleep(0.1)
            print("[MOTION] 电机已激活")
        except Exception as e:
            print("[WARNING] 无法设置stiffness：{}".format(e))
    
    try:
        # ========== 使用NAO内置动画库(更可靠) ==========
        if action_tag in ["joy", "happy"]:
            # 快乐/高兴 - 使用内置joy动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Emotions/Positive/Happy_4")
                    print("[ANIMATION] 播放快乐动画")
                except:
                    # 回退到手动控制
                    motion.setAngles("LShoulderPitch", -1.0, 0.3)
                    motion.setAngles("RShoulderPitch", -1.0, 0.3)
                    time.sleep(0.8)
                    motion.setAngles("LShoulderPitch", 1.5, 0.3)
                    motion.setAngles("RShoulderPitch", 1.5, 0.3)
            else:
                print("[MOCK MOTION] 快乐动画：举起双臂欢呼！")
        
        elif action_tag in ["greeting", "wave"]:
            # 打招呼/挥手 - 使用内置Hey动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Hey_1")
                    print("[ANIMATION] 播放挥手打招呼动画")
                except:
                    # 回退到手动挥手
                    motion.setAngles("RShoulderPitch", -0.5, 0.3)
                    motion.setAngles("RShoulderRoll", -0.3, 0.3)
                    time.sleep(0.5)
                    for _ in range(2):
                        motion.setAngles("RElbowRoll", 1.5, 0.5)
                        time.sleep(0.3)
                        motion.setAngles("RElbowRoll", 0.5, 0.5)
                        time.sleep(0.3)
                    motion.setAngles("RShoulderPitch", 1.5, 0.3)
            else:
                print("[MOCK MOTION] 挥手打招呼")
        
        elif action_tag in ["confirm", "yes", "nodding"]:
            # 确认/点头 - 使用内置Yes动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Yes_1")
                    print("[ANIMATION] 播放点头确认动画")
                except:
                    # 回退到点头动作
                    motion.setAngles("HeadPitch", 0.4, 0.3)
                    time.sleep(0.3)
                    motion.setAngles("HeadPitch", -0.1, 0.3)
                    time.sleep(0.3)
                    motion.setAngles("HeadPitch", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 点头确认")
        
        elif action_tag in ["refuse", "no", "shaking"]:
            # 拒绝/摇头 - 使用内置No动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/No_3")
                    print("[ANIMATION] 播放摇头拒绝动画")
                except:
                    # 回退到摇头动作
                    motion.setAngles("HeadYaw", 0.5, 0.3)
                    time.sleep(0.3)
                    motion.setAngles("HeadYaw", -0.5, 0.3)
                    time.sleep(0.3)
                    motion.setAngles("HeadYaw", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 摇头拒绝")
        
        elif action_tag == "thinking":
            # 思考 - 使用内置Think动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Waiting/Think_1")
                    print("[ANIMATION] 播放思考动画")
                except:
                    # 回退到手托下巴
                    motion.setAngles("HeadPitch", 0.3, 0.2)
                    motion.setAngles("RShoulderPitch", 0.0, 0.3)
                    motion.setAngles("RElbowRoll", 1.5, 0.3)
                    time.sleep(1.5)
                    motion.setAngles("HeadPitch", 0.0, 0.2)
                    motion.setAngles("RShoulderPitch", 1.5, 0.3)
            else:
                print("[MOCK MOTION] 思考姿势")
        
        elif action_tag == "explain":
            # 解释说明 - 使用内置Explain动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Explain_1")
                    print("[ANIMATION] 播放解释说明动画")
                except:
                    # 回退到双手展开
                    motion.setAngles("LShoulderPitch", 0.5, 0.3)
                    motion.setAngles("RShoulderPitch", 0.5, 0.3)
                    motion.setAngles("LElbowRoll", -1.0, 0.3)
                    motion.setAngles("RElbowRoll", 1.0, 0.3)
                    time.sleep(1.2)
                    motion.setAngles("LShoulderPitch", 1.5, 0.3)
                    motion.setAngles("RShoulderPitch", 1.5, 0.3)
            else:
                print("[MOCK MOTION] 解释手势")
        
        elif action_tag in ["pointing", "show"]:
            # 指向/展示 - 使用内置You动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/You_1")
                    print("[ANIMATION] 播放指向展示动画")
                except:
                    # 回退到指向手势
                    motion.setAngles("RShoulderPitch", 0.3, 0.3)
                    motion.setAngles("RElbowRoll", 0.3, 0.3)
                    time.sleep(1.0)
                    motion.setAngles("RShoulderPitch", 1.5, 0.3)
            else:
                print("[MOCK MOTION] 指向展示")
        
        elif action_tag == "excited":
            # 兴奋激动 - 使用内置Enthusiastic动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Enthusiastic_4")
                    print("[ANIMATION] 播放兴奋激动动画")
                except:
                    # 回退到快速挥手
                    for _ in range(3):
                        motion.setAngles("LShoulderPitch", -0.5, 0.5)
                        motion.setAngles("RShoulderPitch", -0.5, 0.5)
                        time.sleep(0.2)
                        motion.setAngles("LShoulderPitch", 1.5, 0.5)
                        motion.setAngles("RShoulderPitch", 1.5, 0.5)
                        time.sleep(0.2)
            else:
                print("[MOCK MOTION] 兴奋激动！")
        
        elif action_tag == "sad":
            # 悲伤 - 低头动作
            if not TEST_MODE:
                motion.setAngles("HeadPitch", 0.5, 0.2)
                time.sleep(1.0)
                motion.setAngles("HeadPitch", 0.0, 0.2)
            else:
                print("[MOCK MOTION] 悲伤低头")
        
        elif action_tag in ["curious", "question"]:
            # 好奇疑问 - 使用内置IDontKnow动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/IDontKnow_1")
                    print("[ANIMATION] 播放好奇疑问动画")
                except:
                    # 回退到歪头动作
                    motion.setAngles("HeadPitch", -0.2, 0.3)
                    motion.setAngles("HeadYaw", 0.3, 0.3)
                    time.sleep(1.0)
                    motion.setAngles("HeadPitch", 0.0, 0.3)
                    motion.setAngles("HeadYaw", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 好奇疑问姿势")
        
        # ========== 扩展动作 ==========
        elif action_tag in ["applause", "clap"]:
            # 鼓掌 - 使用内置Clap动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Clap_1")
                    print("[ANIMATION] 播放鼓掌动画")
                except:
                    # 回退到手动鼓掌
                    for _ in range(3):
                        motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.0, 0.0], 0.5)
                        motion.setAngles(["LElbowRoll", "RElbowRoll"], [-1.5, 1.5], 0.5)
                        time.sleep(0.3)
                        motion.setAngles(["LElbowRoll", "RElbowRoll"], [-0.5, 0.5], 0.5)
                        time.sleep(0.3)
            else:
                print("[MOCK MOTION] 鼓掌👏")
        
        elif action_tag == "celebrate":
            # 庆祝 - 使用Winner动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Winner_1")
                    print("[ANIMATION] 播放庆祝胜利动画")
                except:
                    # 回退到举起双臂
                    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-1.5, -1.5], 0.4)
                    time.sleep(0.5)
                    for _ in range(2):
                        motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.3, -0.3], 0.4)
                        time.sleep(0.3)
                        motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.0, 0.0], 0.4)
                        time.sleep(0.3)
            else:
                print("[MOCK MOTION] 庆祝胜利🎉")
        
        elif action_tag == "bow":
            # 鞠躬 - 使用BowShort动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/BowShort_1")
                    print("[ANIMATION] 播放鞠躬动画")
                except:
                    # 回退到弯腰鞠躬
                    motion.setAngles("HeadPitch", 0.5, 0.3)
                    motion.setAngles("HipPitch", -0.5, 0.3)
                    time.sleep(1.0)
                    motion.setAngles("HeadPitch", 0.0, 0.3)
                    motion.setAngles("HipPitch", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 鞠躬🙇")
        
        elif action_tag in ["goodbye", "bye"]:
            # 再见 - 使用Bye动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Bye_1")
                    print("[ANIMATION] 播放再见挥手动画")
                except:
                    # 回退到挥手告别
                    motion.setAngles("RShoulderPitch", -1.0, 0.3)
                    motion.setAngles("RShoulderRoll", -0.3, 0.3)
                    for _ in range(3):
                        motion.setAngles("RElbowRoll", 1.5, 0.4)
                        time.sleep(0.3)
                        motion.setAngles("RElbowRoll", 0.5, 0.4)
                        time.sleep(0.3)
            else:
                print("[MOCK MOTION] 再见挥手👋")
        
        elif action_tag in ["cheer", "encourage"]:
            # 加油鼓励 - 使用ComeOn动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/ComeOn_1")
                    print("[ANIMATION] 播放加油鼓励动画")
                except:
                    # 回退到握拳加油
                    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.0, 0.0], 0.4)
                    motion.setAngles(["LElbowRoll", "RElbowRoll"], [-1.5, 1.5], 0.4)
                    for _ in range(2):
                        motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, -0.5], 0.5)
                        time.sleep(0.3)
                        motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.0, 0.0], 0.5)
                        time.sleep(0.3)
            else:
                print("[MOCK MOTION] 加油鼓励💪")
        
        elif action_tag in ["sorry", "apologize"]:
            # 抱歉道歉 - 使用Sorry动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Sorry_1")
                    print("[ANIMATION] 播放道歉动画")
                except:
                    # 回退到低头道歉
                    motion.setAngles("HeadPitch", 0.5, 0.3)
                    motion.setAngles("RShoulderPitch", 0.3, 0.3)
                    motion.setAngles("RElbowRoll", 1.0, 0.3)
                    time.sleep(1.5)
                    motion.setAngles("HeadPitch", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 抱歉道歉🙏")
        
        elif action_tag in ["surprised", "shocked"]:
            # 惊讶震惊 - 使用Surprised动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Emotions/Negative/Surprise_1")
                    print("[ANIMATION] 播放惊讶动画")
                except:
                    # 回退到举起双手
                    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, -0.5], 0.6)
                    motion.setAngles(["LShoulderRoll", "RShoulderRoll"], [0.5, -0.5], 0.6)
                    motion.setAngles("HeadPitch", -0.3, 0.6)
                    time.sleep(1.0)
                    motion.setAngles("HeadPitch", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 惊讶震惊😲")
        
        elif action_tag in ["shy", "embarrassed"]:
            # 害羞尴尬 - 使用Shy动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Shy_1")
                    print("[ANIMATION] 播放害羞动画")
                except:
                    # 回退到遮脸害羞
                    motion.setAngles("HeadPitch", 0.3, 0.3)
                    motion.setAngles("HeadYaw", 0.4, 0.3)
                    motion.setAngles(["RShoulderPitch", "RElbowRoll"], [0.0, 1.3], 0.3)
                    time.sleep(1.5)
                    motion.setAngles(["HeadPitch", "HeadYaw"], [0.0, 0.0], 0.3)
            else:
                print("[MOCK MOTION] 害羞尴尬😳")
        
        elif action_tag == "laugh":
            # 大笑 - 使用Laugh动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Emotions/Positive/Laugh_1")
                    print("[ANIMATION] 播放大笑动画")
                except:
                    # 回退到摇头晃脑大笑
                    for _ in range(2):
                        motion.setAngles("HeadYaw", 0.3, 0.4)
                        motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [0.5, 0.5], 0.4)
                        time.sleep(0.4)
                        motion.setAngles("HeadYaw", -0.3, 0.4)
                        time.sleep(0.4)
                    motion.setAngles("HeadYaw", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 大笑😄")
        
        elif action_tag in ["relax", "calm"]:
            # 放松冷静 - 使用Relax动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Waiting/Relaxation_1")
                    print("[ANIMATION] 播放放松动画")
                except:
                    # 回退到放松姿态
                    motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.0, 1.0], 0.2)
                    motion.setAngles("HeadPitch", 0.2, 0.2)
                    time.sleep(2.0)
                    motion.setAngles("HeadPitch", 0.0, 0.2)
            else:
                print("[MOCK MOTION] 放松冷静😌")
        
        elif action_tag == "dance":
            # 跳舞 - 使用Dance动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Enthusiastic_5")
                    print("[ANIMATION] 播放跳舞动画")
                except:
                    # 回退到简单舞蹈
                    for _ in range(2):
                        motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [-0.5, 1.0], 0.4)
                        time.sleep(0.3)
                        motion.setAngles(["LShoulderPitch", "RShoulderPitch"], [1.0, -0.5], 0.4)
                        time.sleep(0.3)
            else:
                print("[MOCK MOTION] 跳舞💃")
        
        elif action_tag in ["sleep", "tired"]:
            # 困倦 - 使用Yawn动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Waiting/Bored_1")
                    print("[ANIMATION] 播放困倦动画")
                except:
                    # 回退到打哈欠
                    motion.setAngles("HeadPitch", 0.5, 0.2)
                    motion.setAngles("RShoulderPitch", 0.0, 0.3)
                    motion.setAngles("RElbowRoll", 1.5, 0.3)
                    time.sleep(2.0)
                    motion.setAngles("HeadPitch", 0.0, 0.2)
            else:
                print("[MOCK MOTION] 困倦打哈欠😴")
        
        # ========== 姿势类动作 ==========
        elif action_tag == "sit":
            # 坐下
            if not TEST_MODE:
                try:
                    posture = services.get('posture')
                    if posture:
                        posture.goToPosture("Sit", 0.8)
                        print("[POSTURE] 坐下姿势")
                    else:
                        # 如果没有posture服务，使用motion
                        motion.setAngles("KneePitch", 2.0, 0.3)
                        time.sleep(1.0)
                        print("[MOTION] 执行坐下动作")
                except Exception as e:
                    print("[WARNING] 坐下动作失败：{}".format(e))
            else:
                print("[MOCK MOTION] 坐下🪑")
        
        elif action_tag == "stand":
            # 站起来
            if not TEST_MODE:
                try:
                    posture = services.get('posture')
                    if posture:
                        posture.goToPosture("Stand", 0.8)
                        print("[POSTURE] 站立姿势")
                    else:
                        motion.setAngles("KneePitch", 0.0, 0.3)
                        time.sleep(1.0)
                        print("[MOTION] 执行站立动作")
                except Exception as e:
                    print("[WARNING] 站立动作失败：{}".format(e))
            else:
                print("[MOCK MOTION] 站起来🧍")
        
        elif action_tag == "crouch":
            # 蹲下
            if not TEST_MODE:
                try:
                    posture = services.get('posture')
                    if posture:
                        posture.goToPosture("Crouch", 0.8)
                        print("[POSTURE] 蹲下姿势")
                    else:
                        motion.setAngles("KneePitch", 1.5, 0.3)
                        time.sleep(1.0)
                        print("[MOTION] 执行蹲下动作")
                except Exception as e:
                    print("[WARNING] 蹲下动作失败：{}".format(e))
            else:
                print("[MOCK MOTION] 蹲下")
        
        elif action_tag == "stretch":
            # 伸展身体 - 使用Stretch动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Waiting/Stretch_1")
                    print("[ANIMATION] 播放伸展动画")
                except:
                    # 回退到伸展手臂
                    motion.setAngles("LShoulderPitch", -1.5, 0.3)
                    motion.setAngles("RShoulderPitch", -1.5, 0.3)
                    time.sleep(1.5)
                    motion.setAngles("LShoulderPitch", 1.5, 0.3)
                    motion.setAngles("RShoulderPitch", 1.5, 0.3)
            else:
                print("[MOCK MOTION] 伸展身体🤸")
        
        elif action_tag == "wipeforehead":
            # 擦额头 - 使用WipeForehead动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/WipeForehead_1")
                    print("[ANIMATION] 播放擦额头动画")
                except:
                    # 回退到手动擦额头
                    motion.setAngles("RShoulderPitch", -0.5, 0.3)
                    motion.setAngles("RElbowRoll", 1.0, 0.3)
                    time.sleep(0.5)
                    motion.setAngles("RShoulderRoll", -0.5, 0.3)
                    time.sleep(0.8)
                    motion.setAngles("RShoulderPitch", 1.5, 0.3)
                    motion.setAngles("RShoulderRoll", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 擦额头💦")
        
        elif action_tag == "sneeze":
            # 打喷嚏 - 使用Sneeze动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Sneeze_1")
                    print("[ANIMATION] 播放打喷嚏动画")
                except:
                    # 回退到打喷嚏动作
                    motion.setAngles("HeadPitch", -0.3, 0.5)
                    time.sleep(0.3)
                    motion.setAngles("HeadPitch", 0.5, 0.8)
                    time.sleep(0.2)
                    motion.setAngles("HeadPitch", 0.0, 0.3)
            else:
                print("[MOCK MOTION] 打喷嚏🤧")
        
        elif action_tag == "scratchhead":
            # 挠头 - 使用ScratchHead动画
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/ScratchHead_1")
                    print("[ANIMATION] 播放挠头动画")
                except:
                    # 回退到手动挠头
                    motion.setAngles("RShoulderPitch", -0.5, 0.3)
                    motion.setAngles("RElbowRoll", 1.5, 0.3)
                    time.sleep(0.5)
                    for _ in range(2):
                        motion.setAngles("RElbowYaw", 0.5, 0.5)
                        time.sleep(0.2)
                        motion.setAngles("RElbowYaw", -0.5, 0.5)
                        time.sleep(0.2)
                    motion.setAngles("RShoulderPitch", 1.5, 0.3)
            else:
                print("[MOCK MOTION] 挠头🤔")
        
        else:
            # 未知动作标签，使用默认动作
            print("[ACTION] 未知动作标签：{}，使用默认greeting动作".format(action_tag))
            if not TEST_MODE and animation:
                try:
                    animation.run("animations/Stand/Gestures/Hey_1")
                except:
                    pass
            else:
                print("[MOCK MOTION] 默认打招呼动作")
    
    except Exception as e:
        print("[ERROR] 动作执行失败：{}".format(e))
        import traceback
        traceback.print_exc()


# ============================================================
# 服务器通信
# ============================================================
def send_to_server(text, image_data=None, audio_data=None):
    """
    向服务器发送请求并接收响应
    
    参数：
        text (str): 用户的文本输入（可选）
        image_data (str): Base64编码的图像（可选）
        audio_data (str): Base64编码的音频（可选）
    
    返回：
        dict: 服务器响应 {"response_text": str, "action_tag": str}
    """
    try:
        # 创建socket连接
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)  # 增加到30秒（处理长对话历史）
        
        print("[CLIENT] 正在连接服务器 {}:{}...".format(SERVER_IP, SERVER_PORT))
        sock.connect((SERVER_IP, SERVER_PORT))
        
        # 准备请求
        request = {
            "text": text or ""
        }
        if image_data:
            request["image_data"] = image_data
        if audio_data:
            request["audio_data"] = audio_data
        
        # 发送请求
        request_json = json.dumps(request, ensure_ascii=False) + '\n'
        sock.sendall(request_json.encode('utf-8'))
        print("[CLIENT] 请求已发送")
        if audio_data:
            print("[CLIENT] 📢 音频数据：{} 字节".format(len(audio_data)))
        if image_data:
            print("[CLIENT] 📷 图像数据：{} 字节".format(len(image_data)))
        
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
        print("[CLIENT] 已收到响应")
        
        sock.close()
        return response
        
    except socket.timeout:
        print("[ERROR] 服务器连接超时")
        return {"response_text": "抱歉，服务器没有响应。", "action_tag": "sad"}
    except Exception as e:
        print("[ERROR] 通信失败：{}".format(e))
        return {"response_text": "抱歉，我失去了连接。", "action_tag": "sad"}


# ============================================================
# 电脑代理模式 - 接收电脑语音指令
# ============================================================
def listen_for_pc_commands(services, tts, video):
    """
    后台线程：监听来自电脑的语音指令
    
    参数：
        services: NAO服务代理
        tts: TTS服务
        video: 视频服务
    """
    try:
        # 创建服务器socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', PC_PROXY_PORT))
        server_socket.listen(5)
        
        print("[PC_PROXY] 监听电脑指令 端口:{}".format(PC_PROXY_PORT))
        
        while True:
            try:
                # 接受连接
                conn, addr = server_socket.accept()
                print("[PC_PROXY] 收到电脑连接：{}".format(addr))
                
                # 接收数据
                data = b''
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b'\n' in chunk:
                        break
                
                # 解析指令
                command = json.loads(data.decode('utf-8'))
                text = command.get('text', '')
                needs_vision = command.get('needs_vision', False)
                
                print("[PC_PROXY] 收到文本：{}".format(text))
                print("[PC_PROXY] 需要视觉：{}".format(needs_vision))
                
                # 处理指令
                process_pc_command(text, needs_vision, services, tts, video)
                
                conn.close()
                
            except Exception as e:
                print("[PC_PROXY] 处理错误：{}".format(e))
                try:
                    conn.close()
                except:
                    pass
                
    except Exception as e:
        print("[PC_PROXY] 监听错误：{}".format(e))


def process_pc_command(text, needs_vision, services, tts, video):
    """
    处理来自电脑的指令
    
    参数：
        text: 文本指令
        needs_vision: 是否需要视觉
        services: NAO服务
        tts: TTS服务
        video: 视频服务
    """
    try:
        print("[PC_PROXY] 开始处理指令...")
        
        # 如果需要视觉，拍照
        image_data = None
        if needs_vision:
            print("[PC_PROXY] 触发拍照...")
            tts.say("Let me take a look.")
            image_data = capture_image(video)
            if image_data:
                print("[PC_PROXY] 拍照成功")
            else:
                print("[PC_PROXY] 拍照失败")
        
        # 发送到服务器
        print("[PC_PROXY] 发送到服务器...")
        response = send_to_server(text, image_data, None)
        
        # 获取响应
        response_text = response['response_text']
        action_tag = response['action_tag']
        
        print("[PC_PROXY] 收到响应：{}".format(response_text[:50]))
        print("[PC_PROXY] 动作标签：{}".format(action_tag))
        
        # 清理文本
        clean_response = clean_text_for_tts(response_text)
        
        if clean_response:
            # 并行执行动作和语音
            def do_action():
                execute_action(action_tag, services)
            
            def do_speech():
                tts.say(clean_response)
            
            action_thread = threading.Thread(target=do_action)
            speech_thread = threading.Thread(target=do_speech)
            
            action_thread.start()
            speech_thread.start()
            
            action_thread.join()
            speech_thread.join()
            
            print("[PC_PROXY] ✅ 执行完成")
        else:
            print("[PC_PROXY] ⚠️ 响应文本为空")
            
    except Exception as e:
        print("[PC_PROXY] 执行错误：{}".format(e))
        import traceback
        traceback.print_exc()


# ============================================================
# 主交互循环
# ============================================================
def main():
    """
    NAO机器人客户端的主交互循环
    """
    print("=" * 60)
    print("NAO机器人客户端")
    print("兼容Python 2.7 - 机器人端")
    if TEST_MODE:
        print("测试模式：已启用（模拟机器人）")
    else:
        print("真实模式：运行在NAO机器人上")
    print("=" * 60)
    
    # 初始化机器人服务
    services = init_robot_services()
    tts = services['tts']
    video = services['video']
    
    # 打招呼
    print("\n[ROBOT] 机器人已就绪！")
    sys.stdout.flush()
    
    try:
        print("[DEBUG] 尝试TTS测试：'Hello, I am ready.'")
        sys.stdout.flush()
        tts.say("Hello, I am ready.")
        print("[DEBUG] TTS测试完成")
        sys.stdout.flush()
    except Exception as e:
        print("[ERROR] TTS测试失败：{}".format(e))
        sys.stdout.flush()
        import traceback
        traceback.print_exc()
    
    # 启动电脑代理监听线程
    if ENABLE_PC_PROXY and not TEST_MODE:
        print("[PC_PROXY] ✅ 启用电脑语音代理模式")
        proxy_thread = threading.Thread(
            target=listen_for_pc_commands,
            args=(services, tts, video)
        )
        proxy_thread.daemon = True  # Python 2.7兼容方式
        proxy_thread.start()
        print("[PC_PROXY] 后台监听已启动（端口：{}）".format(PC_PROXY_PORT))
    elif ENABLE_PC_PROXY and TEST_MODE:
        print("[PC_PROXY] ⚠️ 测试模式下禁用电脑代理")
    
    # 主交互循环
    while True:
        try:
            # ========== 获取用户输入 ==========
            print("\n" + "=" * 60)
            
            user_text = None
            audio_data = None
            
            # 方式1：使用录音+服务器识别（推荐）
            if USE_AUDIO_RECORDING and not TEST_MODE:
                print("[机器人] 🎤 请说话，我在录音...")
                tts.say("我在听，请说话")
                audio_data = record_audio(services, duration=RECORDING_DURATION)
                if audio_data:
                    print("[SUCCESS] 录音完成，将发送到服务器识别")
                    user_text = ""  # 音频模式下文本可为空，大模型会从音频提取
                else:
                    print("[WARNING] 录音失败，切换到键盘输入")
                    user_text = listen_for_speech(services, timeout=15)
            
            # 方式2：使用NAO本地语音识别（备用）
            elif USE_SPEECH_RECOGNITION and not TEST_MODE:
                print("[机器人] 我在听，请说话...")
                tts.say("我在听")
                user_text = listen_for_speech(services, timeout=15)
            
            # 方式3：键盘输入（测试模式或默认）
            else:
                user_text = listen_for_speech(services, timeout=15)
            
            # 检查是否成功获取输入
            if not user_text and not audio_data:
                if not TEST_MODE:
                    tts.say("抱歉，我没听清楚，请再说一次")
                continue
            
            # 检查退出指令
            if user_text and user_text.lower() in ['quit', 'exit', 'bye', u'再见']:
                tts.say("再见！下次见。")
                break
            
            # ========== 检查视觉需求 ==========
            needs_vision = False
            if user_text:
                needs_vision = any(keyword in user_text.lower() for keyword in VISION_KEYWORDS)

            image_data = None
            if needs_vision:
                if EXPERIMENT_CONDITION == "vision":
                    # 实验组：拍照并分析
                    print("[TRIGGER] 实验组：检测到视觉关键词，开始拍照")
                    tts.say("Let me take a look.")
                    image_data = capture_image(video)
                else:
                    # 对照组：不拍照，直接告知用户
                    print("[TRIGGER] 对照组：视觉关键词被屏蔽，不拍照")
                    tts.say("I cannot see things around me. But please tell me what you have and I will help you.")
            
            # ========== 发送请求到服务器 ==========
            print("[CLIENT] 正在发送到服务器...")
            if audio_data:
                print("[CLIENT] 模式：🎤 音频模式（Qwen-Audio识别）")
            response = send_to_server(user_text, image_data, audio_data)
            
            # 获取响应文本和动作
            response_text = response['response_text']
            action_tag = response['action_tag']
            personality = response.get('personality', 'friendly')
            
            print("[RESPONSE] {}".format(response_text))
            print("[ACTION] 动作标签: {} | 性格: {}".format(action_tag, personality))
            
            # 清理文本用于TTS（移除emoji等NAOqi无法处理的字符）
            print("[DEBUG] 原始响应文本长度: {} 字符".format(len(response_text)))
            clean_response = clean_text_for_tts(response_text)
            print("[DEBUG] 清理后文本长度: {} 字符".format(len(clean_response)))
            print("[DEBUG] 清理后文本预览: {}".format(clean_response[:100]))
            
            if not clean_response:
                print("[WARNING] 清理后的文本为空，跳过语音和动作")
                continue
            
            # ========== 同时执行动作和语音输出（并行）==========
            print("[TTS] 正在朗读: {}".format(clean_response[:50]))
            print("[ACTION] 执行动作: {}".format(action_tag))
            
            try:
                # 使用线程并行执行动作和TTS
                # 这样NAO可以一边做动作一边说话，更自然！
                
                # 定义动作执行函数
                def do_action():
                    execute_action(action_tag, services)
                
                # 定义TTS执行函数
                def do_speech():
                    tts.say(clean_response)
                
                # 创建并启动两个线程
                action_thread = threading.Thread(target=do_action)
                speech_thread = threading.Thread(target=do_speech)
                
                # 同时启动动作和语音
                action_thread.start()
                speech_thread.start()
                
                # 等待两者都完成
                action_thread.join()
                speech_thread.join()
                
                print("[SUCCESS] 动作和语音输出完成（并行执行）")
                
            except Exception as e:
                print("[ERROR] 动作或TTS失败: {}".format(e))
                import traceback
                traceback.print_exc()
            
        except KeyboardInterrupt:
            print("\n[ROBOT] 用户中断")
            tts.say("再见！")
            break
        except Exception as e:
            print("[ERROR] 循环错误：{}".format(e))
            tts.say("抱歉，出现了一些问题。")
    
    print("\n[ROBOT] 客户端已停止")


# ============================================================
# 程序入口
# ============================================================
if __name__ == "__main__":
    main()
