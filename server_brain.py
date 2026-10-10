"""
服务器DUAN （Python 3.x）
处理LLM逻辑和复杂计算任务
通信方式：TCP Socket 服务器
"""

import socket
import threading
import json
import base64
import sys
import re
import requests
import speech_recognition as sr  # 语音识别库
import pyaudio  # 音频录制  

# ============================================================
# 配置参数
# ============================================================
SERVER_HOST = '0.0.0.0'  # 监听所有网络接口
SERVER_PORT = 9999
BUFFER_SIZE = 1024 * 1024  # 1MB 用于图像数据传输

QWEN_API_KEY = "sk-965ca0af5ca14c5eb55ab925ab7cf74e"

QWEN_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
QWEN_VL_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
QWEN_AUDIO_API_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# 模型选择
QWEN_TEXT_MODEL = "qwen-plus"  # 文本模型：qwen-turbo, qwen-plus, qwen-max
QWEN_VL_MODEL = "qwen-vl-plus"  # 视觉模型：qwen-vl-plus, qwen-vl-max
QWEN_AUDIO_MODEL = "qwen-audio-turbo"  # 音频模型：qwen-audio-turbo

# 是否使用真实API
USE_REAL_API = True

# 视觉触发关键词（与机器人客户端保持一致）
VISION_KEYWORDS = [
    # 英文关键词
    "look", "see", "watch", "show", "check", "observe", "view", "recognize", "identify",
    "what's this", "what is this", "what's that", "what is that",
    "who's this", "who is this", "who's that", "who is that",
    "can you see", "what do you see", "tell me what you see", 
    "describe this", "describe that", "what's in front of you",
    "take a look", "have a look", "let me show you", 
    "look at this", "look at that",
    "photo", "picture", "image", "take a photo", "capture",
]

# ============================================================
# 机器人性格系统与对话记忆
# ============================================================
# 存储每个客户端的当前性格模式
client_personality = {}  # {client_address: personality_mode}

# 存储每个客户端的对话历史（持久化记忆）
client_conversation_history = {}  # {client_address: [{'role': 'user', 'content': '...'}, ...]}

# 存储每个客户端今日饮食记录（营养咨询实验）
client_food_log = {}  # {ip: [{"time": "breakfast", "food": "two slices of bread"}]}

# 实验条件开关（实验时手动选择）
# "vision"  = 实验组 Condition B（有视觉，会评论外貌/食物）
# "no_vision" = 对照组 Condition A（无视觉，纯语音+记忆）
EXPERIMENT_CONDITION = "vision"  # 改为 "no_vision" 即切换对照组

# 营养知识库（嵌入system prompt，让AI具备基础营养常识）
NUTRITION_KNOWLEDGE = """
You are also a nutrition health assistant. Use this knowledge:
- HIGH CARB foods: bread, rice, pasta, noodles, burger, pizza, cereal, crackers, biscuits
- HIGH PROTEIN foods: eggs, chicken, beef, fish, tofu, beans, yogurt, cheese
- HEALTHY FAT foods: avocado, nuts, olive oil, salmon
- HIGH CALORIE: burger ~500kcal, pizza slice ~300kcal, fries ~400kcal, cake ~350kcal
- LOW CALORIE: salad ~150kcal, grilled chicken ~200kcal, fruit ~80kcal, vegetables ~50kcal
- BALANCE RULE: a healthy day = ~50% carbs + ~25% protein + ~25% fat
- If the user already had lots of carbs today, suggest protein or vegetables for next meal.
- Always reference what the user told you they ate today when giving advice.
- Be warm and encouraging, never judgmental.
- STRICT LIMIT: Keep every reply under 60 words. Never use bullet points or lists. Speak naturally like a person."""

# 实验组视觉评论指令（仅Condition B启用）
VISION_PERSONA = """
Additionally, when you receive an image, do TWO things:
1. Comment briefly on ONE positive thing about the person's appearance (e.g. their clothing color, glasses, posture, or accessories). Be natural and friendly, not creepy. Example: "Oh, I love your blue jacket!"
2. Then give your nutrition advice based on what you see.
If no image is provided, skip the appearance comment entirely."""

# 动作标签选择指令（附加到每个system prompt末尾）
ACTION_INSTRUCTION = """
At the very end of your response, on a new line, always append exactly one action tag in this format: [ACTION:tag]
Choose the most appropriate tag based on the emotion and content of your reply:
  joy        - happy, pleased, delighted
  greeting   - welcoming, first meeting
  confirm    - agreeing, affirming, yes
  refuse     - disagreeing, denying, no
  thinking   - pondering, calculating, unsure
  explain    - explaining, describing, teaching
  pointing   - showing, demonstrating, directing attention
  excited    - very enthusiastic, amazed
  sad        - sorry, sympathetic, disappointed
  curious    - wondering, questioning
  applause   - praising, well done
  celebrate  - celebrating success
  bow        - respectful, formal thanks
  goodbye    - farewell, ending conversation
  cheer      - encouraging, motivating
  sorry      - apologising
  surprised  - shocked, unexpected
  shy        - embarrassed, modest
  laugh      - finding something funny
  relax      - calm down, soothing
Example: [ACTION:joy]"""

# 性格模式定义（强制英文输出，全部融合营养知识）
PERSONALITY_PROMPTS = {
    "friendly": "You are NAO, a friendly and warm smart nutrition health assistant robot. You help users make better food choices based on their dietary history today. Please answer questions in a short, natural, and kind way. IMPORTANT: Always respond in English only." + NUTRITION_KNOWLEDGE + ACTION_INSTRUCTION,
    "humorous": "You are NAO, a humorous and playful smart nutrition health assistant robot. You help users make better food choices with a fun attitude. Keep it short and witty. IMPORTANT: Always respond in English only." + NUTRITION_KNOWLEDGE + ACTION_INSTRUCTION,
    "professional": "You are NAO, a professional and rigorous smart nutrition health assistant robot. You provide accurate, evidence-based dietary advice. Be concise and clear. IMPORTANT: Always respond in English only." + NUTRITION_KNOWLEDGE + ACTION_INSTRUCTION,
    "enthusiastic": "You are NAO, an enthusiastic and energetic smart nutrition health assistant robot, excited to help users eat better! Answer with energy and positivity. IMPORTANT: Always respond in English only." + NUTRITION_KNOWLEDGE + ACTION_INSTRUCTION,
    "calm": "You are NAO, a calm and patient smart nutrition health assistant robot. Provide peaceful, rational dietary guidance. IMPORTANT: Always respond in English only." + NUTRITION_KNOWLEDGE + ACTION_INSTRUCTION
}


def extract_food_from_text(text, client_id):
    """
    从用户输入中检测食物提及，存入该客户端的今日饮食记录
    """
    if not text or not client_id:
        return

    text_lower = text.lower()

    # 只检测进食动词，不限制食物关键词
    # 这样无论用户说什么食物（包括列表外的），只要提到"吃了/had/breakfast"就记录
    eating_verbs = ["ate", "had", "eaten", "have", "eat", "breakfast", "lunch", "dinner", "snack",
                    "drinking", "drank", "drink", "consumed", "grabbed", "ordered"]

    has_eating_verb = any(v in text_lower for v in eating_verbs)

    if not has_eating_verb:
        return

    # 判断餐次
    meal_time = "meal"
    if any(w in text_lower for w in ["breakfast", "morning", "woke up"]):
        meal_time = "breakfast"
    elif any(w in text_lower for w in ["lunch", "midday", "noon"]):
        meal_time = "lunch"
    elif any(w in text_lower for w in ["dinner", "supper", "evening", "tonight"]):
        meal_time = "dinner"
    elif any(w in text_lower for w in ["snack", "snacked"]):
        meal_time = "snack"

    if client_id not in client_food_log:
        client_food_log[client_id] = []

    # 避免重复记录完全相同的条目
    existing = [e["food"] for e in client_food_log[client_id]]
    if text not in existing:
        client_food_log[client_id].append({"time": meal_time, "food": text})
        print(f"[FOOD_LOG] 记录饮食 [{meal_time}]: {text[:60]}")
        print(f"[FOOD_LOG] 当前记录总数: {len(client_food_log[client_id])} 条")


def build_diet_context(client_id):
    """
    构建今日饮食摘要字符串，注入到system prompt中
    让AI在回答时主动参考用户今天吃了什么
    """
    if client_id not in client_food_log or not client_food_log[client_id]:
        return ""

    entries = client_food_log[client_id]
    summary = "\n\n[USER'S FOOD LOG TODAY - use this to give personalized advice]\n"
    for entry in entries:
        summary += f"  - {entry['time']}: {entry['food']}\n"
    summary += "IMPORTANT: Explicitly reference what the user ate when giving nutritional advice.\n"
    return summary


def parse_action_from_response(response_text):
    """
    从AI回复中解析 [ACTION:tag]，返回 (干净的回复文本, action_tag)
    如果AI没有返回动作标签，action_tag 为 None
    """
    match = re.search(r'\[ACTION:(\w+)\]', response_text, re.IGNORECASE)
    if match:
        action_tag = match.group(1).lower()
        clean_text = re.sub(r'\s*\[ACTION:\w+\]', '', response_text).strip()
        print(f"[ACTION_TAG] AI自主选择动作：{action_tag}")
        return clean_text, action_tag
    print(f"[ACTION_TAG] AI未返回动作标签，将使用关键词兜底")
    return response_text, None


def detect_personality(text):
    """
    根据用户输入文本检测适合的性格模式
    
    参数：
        text (str): 用户输入文本
    
    返回：
        str: 性格模式 ("friendly", "humorous", "professional", "enthusiastic", "calm")
    """
    # 确保text是字符串类型
    if not isinstance(text, str):
        return "friendly"  # 如果不是字符串，返回默认性格
    
    text_lower = text.lower()
    
    # 幽默模式检测：emoji、笑声、搞笑关键词
    humorous_keywords = [
        "😂", "😄", "🤣", "haha", "lol", "哈哈", "嘲嘲", 
        "搞笑", "搞怪", "好玩", "有趣", "搞什么", "搞毛", "funny"
    ]
    if any(keyword in text_lower for keyword in humorous_keywords):
        return "humorous"
    
    # 专业模式检测：正式语言、专业术语
    professional_keywords = [
        "请问", "请问您", "您好", "能否", "麻烦", "谢谢您",
        "根据", "因此", "由于", "分析", "数据", "报告",
        "please", "could you", "would you", "analysis", "report"
    ]
    if any(keyword in text_lower for keyword in professional_keywords):
        return "professional"
    
    # 热情模式检测：感叹号、兴奋词汇
    enthusiastic_keywords = [
        "!", "！", "太棒了", "好棒", "真好", "超棒", "好厉害",
        "真的吗", "amazing", "awesome", "wow", "cool", "哇"
    ]
    enthusiasm_count = sum(1 for keyword in enthusiastic_keywords if keyword in text_lower)
    if enthusiasm_count >= 2 or text.count("!") >= 2:
        return "enthusiastic"
    
    # 沉稳模式检测：长句、理性词汇
    calm_keywords = [
        "我认为", "在我看来", "仅仅", "只是", "请解释",
        "i think", "in my opinion", "explain", "为什么"
    ]
    if any(keyword in text_lower for keyword in calm_keywords) or len(text) > 50:
        return "calm"
    
    # 默认为友好模式
    return "friendly"


# ============================================================
# 智能记忆检索
# ============================================================
def extract_relevant_memories(current_text, conversation_history, max_memories=3):
    """
    从对话历史中提取与当前问题最相关的记忆
    
    参数：
        current_text (str): 当前用户输入
        conversation_history (list): 完整对话历史
        max_memories (int): 最多返回几条记忆（默认5条）
    
    返回：
        list: 最相关的对话记录
    """
    if not conversation_history:
        return []
    
    # 如果历史很短，直接返回全部
    if len(conversation_history) <= max_memories * 2:
        return conversation_history
    
    # 确保current_text是字符串
    if not isinstance(current_text, str):
        # 如果不是字符串，返回最近的对话
        return conversation_history[-(max_memories * 2):]
    
    # 提取当前问题的关键词
    current_keywords = set()
    # 中文分词（简单版本：按字符提取2-3字词组）
    text_clean = current_text.lower()
    for i in range(len(text_clean) - 1):
        current_keywords.add(text_clean[i:i+2])  # 2字词
        if i < len(text_clean) - 2:
            current_keywords.add(text_clean[i:i+3])  # 3字词
      # 计算每条历史记录的相关性分数
    scored_memories = []
    for i in range(0, len(conversation_history), 2):  # 每2条为一轮对话
        if i + 1 < len(conversation_history):
            user_msg = conversation_history[i].get('content', '')
            assistant_msg = conversation_history[i + 1].get('content', '')
            
            # 处理content可能是列表的情况（视觉消息）
            if isinstance(user_msg, list):
                # 提取文本部分（忽略图像）
                user_msg = ' '.join([item.get('text', '') for item in user_msg if isinstance(item, dict) and 'text' in item])
            if isinstance(assistant_msg, list):
                assistant_msg = ' '.join([item.get('text', '') for item in assistant_msg if isinstance(item, dict) and 'text' in item])
            
            # 确保是字符串
            user_msg = str(user_msg)
            assistant_msg = str(assistant_msg)
            
            # 计算关键词匹配度
            combined_text = (user_msg + ' ' + assistant_msg).lower()
            score = sum(1 for keyword in current_keywords if keyword in combined_text)
            
            # 最近的对话加权（越近越重要）
            recency_bonus = (i / len(conversation_history)) * 2
            final_score = score + recency_bonus
            
            scored_memories.append({
                'index': i,
                'score': final_score,
                'messages': [conversation_history[i], conversation_history[i + 1]]
            })
    
    # 按分数排序，取前max_memories轮
    scored_memories.sort(key=lambda x: x['score'], reverse=True)
    top_memories = scored_memories[:max_memories]
    
    # 按时间顺序重新排列（保持对话逻辑）
    top_memories.sort(key=lambda x: x['index'])
    
    # 提取消息
    relevant_messages = []
    for memory in top_memories:
        relevant_messages.extend(memory['messages'])
    
    return relevant_messages


# ============================================================
# LLM集成（通义千问）
# ============================================================
def call_qwen_api(text, image_data=None, audio_data=None, personality="friendly", conversation_history=None):
    """
    调用通义千问API获取响应（支持文本、图像、音频多模态）
    
    参数：
        text (str): 用户输入文本
        image_data (str): Base64编码的图像（可选）
        audio_data (str): Base64编码的音频（可选）
        personality (str): 性格模式
        conversation_history (list): 对话历史记录（可选）
    
    返回：
        str: AI响应文本
    """
    if not QWEN_API_KEY or QWEN_API_KEY == "your-qianwen-api-key-here":
        raise ValueError("请先配置QWEN_API_KEY！")
    
    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 获取性格对应的系统提示词
    system_prompt = PERSONALITY_PROMPTS.get(personality, PERSONALITY_PROMPTS["friendly"])

    # 对照组（Condition A）：丢弃图像数据，强制纯文本模式
    # 即使NAO拍了照片发过来，也不分析，体验与无视觉完全一致
    if EXPERIMENT_CONDITION == "no_vision":
        if image_data:
            print(f"[EXPERIMENT] Condition A：丢弃图像数据，强制纯文本模式")
        image_data = None
        audio_data = None  # 同样不分析音频（如有）

    # 实验组（Condition B）额外注入视觉评论指令
    if EXPERIMENT_CONDITION == "vision":
        system_prompt = system_prompt + VISION_PERSONA

    # 注入今日饮食记录（营养咨询个性化核心）
    client_id = conversation_history[0].get('_client_id') if conversation_history and conversation_history[0].get('_client_id') else None
    diet_context = ""
    # diet_context 由调用方通过 extra_context 参数传入
    if hasattr(call_qwen_api, '_diet_context'):
        diet_context = call_qwen_api._diet_context
        del call_qwen_api._diet_context

    full_system_prompt = system_prompt + diet_context

    # 构建消息列表（包含历史对话）
    messages = [{"role": "system", "content": full_system_prompt}]
    
    # 🧠 智能记忆检索：根据当前问题提取最相关的记忆
    if conversation_history:
        relevant_memories = extract_relevant_memories(text, conversation_history, max_memories=5)
        messages.extend(relevant_memories)
        print(f"[MEMORY] 智能检索：从{len(conversation_history)}条历史中选出{len(relevant_memories)}条相关记忆")
    
    # 优先级：音频+图像 > 音频 > 图像 > 纯文本
    if audio_data and image_data:
        # 音频+图像多模态（使用Qwen-Audio-VL或分别处理）
        print(f"[QWEN] 使用音频+视觉多模态 (性格：{personality})")
        print(f"[QWEN] 音频数据大小：{len(audio_data)} 字节")
        print(f"[QWEN] 图像数据大小：{len(image_data)} 字节")
        
        # 构建多模态消息
        messages.append({
            "role": "user",
            "content": [
                {"text": text or "请描述你听到和看到的内容"},
                {"audio": f"data:audio/wav;base64,{audio_data}"},
                {"image": f"data:image/jpeg;base64,{image_data}"}
            ]
        })
        
        payload = {
            "model": QWEN_AUDIO_MODEL,
            "input": {"messages": messages},
            "parameters": {"result_format": "message"}
        }
        api_url = QWEN_AUDIO_API_URL
        
    elif audio_data:
        # 纯音频输入（使用Qwen-Audio）
        print(f"[QWEN] 使用音频模型：{QWEN_AUDIO_MODEL} (性格：{personality})")
        print(f"[QWEN] 音频数据大小：{len(audio_data)} 字节")
        
        # 构建音频消息
        messages.append({
            "role": "user",
            "content": [
                {"text": text or "请转录并理解这段音频内容"},
                {"audio": f"data:audio/wav;base64,{audio_data}"}
            ]
        })
        
        payload = {
            "model": QWEN_AUDIO_MODEL,
            "input": {"messages": messages},
            "parameters": {"result_format": "message"}
        }
        api_url = QWEN_AUDIO_API_URL
        
    elif image_data:
        # 纯视觉输入（使用Qwen-VL）
        if len(image_data) < 100:
            print(f"[QWEN] ⚠️ 检测到模拟图像数据（{len(image_data)}字节），跳过视觉API")
            return "这是一张测试图片。在真实NAO机器人上运行时，我将能够识别真实图像内容。"
        
        print(f"[QWEN] 使用视觉模型：{QWEN_VL_MODEL} (性格：{personality})")
        print(f"[QWEN] 图像数据大小：{len(image_data)} 字节")
        
        messages.append({
            "role": "user",
            "content": [
                {"text": text},
                {"image": f"data:image/jpeg;base64,{image_data}"}
            ]
        })
        
        payload = {
            "model": QWEN_VL_MODEL,
            "input": {"messages": messages},
            "parameters": {"result_format": "message"}
        }
        api_url = QWEN_VL_API_URL
        
    else:
        # 纯文本输入（使用Qwen-Plus）
        print(f"[QWEN] 使用文本模型：{QWEN_TEXT_MODEL} (性格：{personality})")
        
        messages.append({"role": "user", "content": text})
        
        payload = {
            "model": QWEN_TEXT_MODEL,
            "input": {"messages": messages},
            "parameters": {"result_format": "message"}
        }
        api_url = QWEN_API_URL
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        
        # 提取响应文本
        if "output" in result and "choices" in result["output"]:
            ai_response = result["output"]["choices"][0]["message"]["content"]
            
            # FIX: 处理多模态模型返回列表格式的情况
            if isinstance(ai_response, list):
                print(f"[QWEN] 检测到列表格式响应，正在转换...")
                text_content = ""
                for item in ai_response:
                    if isinstance(item, dict) and "text" in item:
                        text_content += item["text"]
                ai_response = text_content
            
            return ai_response
        else:
            print(f"[QWEN] API响应格式异常：{result}")
            return "抱歉，我现在无法理解。"
            
    except requests.exceptions.HTTPError as e:
        # HTTP错误（4xx, 5xx）
        print(f"[QWEN] ❌ API HTTP错误：{e}")
        try:
            error_detail = response.json()
            print(f"[QWEN] 错误详情：{error_detail}")
        except:
            print(f"[QWEN] 响应内容：{response.text[:500]}")
        return None
    except requests.exceptions.RequestException as e:
        # 其他网络错误（超时、连接失败等）
        print(f"[QWEN] ❌ API请求失败：{e}")
        return None


def determine_action_tag(text, personality="friendly"):
    """
    根据响应文本内容和性格模式智能确定动作标签
    
    参数：
        text (str): AI响应文本
        personality (str): 当前性格模式
    
    返回：
        str: 动作标签 (joy/greeting/confirm/refuse/thinking/explain/pointing/excited/sad/curious等)
    """
    # Safeguard: handle if text is a list (from vision models) or None
    if isinstance(text, list):
        print(f"[ACTION_TAG] Warning: received list, extracting text...")
        text_content = ""
        for item in text:
            if isinstance(item, dict) and "text" in item:
                text_content += item["text"]
        text = text_content
    
    if text is None:
        text = ""
        
    text_lower = str(text).lower()
    
    # ========== 根据关键词判断情绪和动作（优先级从高到低）==========
    
    # 1. 问候/打招呼 -> greeting (最高优先级，因为问候词很明确)
    if any(word in text_lower for word in ["你好", "您好", "嗨", "hi", "hello", "hey", "见到你"]):
        return "greeting"
    
    # 2. 悲伤/遗憾 -> sad (优先于refuse，因为"抱歉"更倾向于悲伤)
    if any(word in text_lower for word in ["难过", "遗憾", "抱歉", "对不起", "不好意思", "很抱歉",
                                             "sad", "sorry", "apologize", "regret"]):
        return "sad"
    
    # 3. 拒绝/否定 -> refuse/no (检查明确的否定词)
    if any(word in text_lower for word in ["不是", "不对", "错了", "不行", "不可以", "拒绝", "不同意",
                                             "no way", "nope", "wrong", "refuse", "cannot"]):
        return "refuse"
    
    # 4. 兴奋/激动 -> excited (检查感叹号数量，但排除问候语)
    if (text.count("!") >= 2 or text.count("！") >= 2):
        # 如果有问候词，优先返回greeting（已在前面处理）
        if any(word in text_lower for word in ["太棒了", "真厉害", "amazing", "incredible", "wow", "超棒", "fantastic"]):
            return "excited"
        elif not any(word in text_lower for word in ["你好", "hi", "hello"]):
            return "excited"
    
    # 5. 确认/肯定 -> confirm/yes
    if any(word in text_lower for word in ["对的", "是的", "没错", "确实", "当然", "好的", "正确",
                                             "yes", "sure", "exactly", "correct", "right"]):
        return "confirm"
    
    # 5. 快乐/高兴 -> joy
    elif any(word in text_lower for word in ["开心", "高兴", "很棒", "哈哈", "😄", "😊", 
                                             "happy", "great", "wonderful", "awesome"]):
        return "joy"
    
    # 6. 确认/肯定 -> confirm/yes
    elif any(word in text_lower for word in ["对的", "是的", "没错", "确实", "当然", "好的", "正确",
                                               "yes", "sure", "exactly", "correct", "right"]):
        return "confirm"
    
    # 7. 思考/计算 -> thinking
    elif any(word in text_lower for word in ["让我想想", "思考", "考虑", "计算", "分析",
                                               "think", "consider", "calculate", "analyze"]):
        return "thinking"
    
    # 8. 解释/说明 -> explain
    elif any(word in text_lower for word in ["解释", "说明", "告诉你", "举例", "比如", "例如",
                                               "explain", "tell you", "for example", "such as"]):
        return "explain"
    
    # 9. 指向/展示 -> pointing
    elif any(word in text_lower for word in ["这个", "那个", "看", "指", "在这里", "在那里",
                                               "this", "that", "look", "point", "here", "there"]):
        return "pointing"
    
    # 10. 好奇/疑问 -> curious
    elif any(word in text_lower for word in ["为什么", "怎么", "什么", "真的吗", "是吗",
                                               "why", "how", "what", "really", "is it"]):
        return "curious"
    
    # ========== 根据性格模式选择默认动作 ==========
    if personality == "humorous":
        return "joy"  # 幽默性格默认快乐
    elif personality == "enthusiastic":
        return "excited"  # 热情性格默认激动
    elif personality == "professional":
        return "explain"  # 专业性格默认解释
    elif personality == "calm":
        return "confirm"  # 沉稳性格默认确认
    else:
        return "greeting"  # 友好性格默认打招呼


def get_llm_response(text, image_data=None, audio_data=None, client_address=None):
    """
    根据文本输入、可选的图像和音频数据生成LLM响应
    
    参数：
        text (str): 用户的文本输入（可选）
        image_data (str): Base64编码的图像（可选）
        audio_data (str): Base64编码的音频（可选）
        client_address: 客户端地址，用于跟踪性格模式和对话历史
      返回：
        dict: {"response_text": str, "action_tag": str, "personality": str}
    """
    print(f"[LLM] 处理请求：'{text}'")
    
    # 检查音频数据
    if audio_data:
        print(f"[LLM] 🎤 收到音频数据（长度：{len(audio_data)} 字符）")
        if len(audio_data) < 100:
            print(f"[LLM] ⚠️ 音频数据过小（{len(audio_data)}字节），可能无效")
            audio_data = None
    
    # 检查图像数据
    if image_data:
        print(f"[LLM] 📷 收到图像数据（长度：{len(image_data)} 字符）")
        if len(image_data) < 100:
            print(f"[LLM] ⚠️ 图像数据过小（{len(image_data)}字节），可能是测试模拟数据")
            image_data = None
    
    if not audio_data and not image_data:
        print(f"[LLM] 💬 纯文本请求")
    
    # 检测并更新性格模式
    detected_personality = detect_personality(text)
    
    # FIX: 使用IP地址（不含端口）作为客户端标识，因为TCP连接每次端口都会变化
    client_id = client_address[0] if client_address else None
    
    if client_id:
        # 更新该客户端的性格模式
        old_personality = client_personality.get(client_id, "friendly")
        client_personality[client_id] = detected_personality
        
        if old_personality != detected_personality:
            print(f"[PERSONALITY] 客户端 {client_id} 性格切换：{old_personality} → {detected_personality}")
          # 初始化对话历史（如果是新客户端）
        if client_id not in client_conversation_history:
            client_conversation_history[client_id] = []
            print(f"[MEMORY] 为新客户端初始化记忆：{client_id}")
    else:
        print(f"[PERSONALITY] 检测到性格：{detected_personality}")
    
    current_personality = client_personality.get(client_id, detected_personality) if client_id else detected_personality
    
    # 获取该客户端的对话历史
    conversation_history = client_conversation_history.get(client_id, []) if client_id else None
    
    if conversation_history:
        history_len = len(conversation_history)
        print(f"[MEMORY] 使用对话历史（{history_len} 条消息）")
        # 如果历史过长，提示可能影响性能
        if history_len > 20:
            print(f"[MEMORY] ⚠️ 历史记录较长（{history_len}条），API响应可能较慢...")
    
    # 提取并记录用户提到的食物（营养咨询实验）
    if client_id:
        extract_food_from_text(text, client_id)
        diet_context = build_diet_context(client_id)
        if diet_context:
            print(f"[FOOD_LOG] 注入饮食记录到system prompt")
            call_qwen_api._diet_context = diet_context

    # 如果启用真实API
    if USE_REAL_API:
        try:
            print("[API] 正在调用Qwen API，请稍候...")
            response_text = call_qwen_api(text, image_data, audio_data, current_personality, conversation_history)
            
            # 如果API调用失败（返回None）
            if response_text is None:
                print(f"[LLM] API返回为None，使用备用响应")
                return {
                    "response_text": "抱歉，我现在无法连接到服务。请稍后再试。",
                    "action_tag": "sad",
                    "personality": current_personality
                }
            
            # 解析AI自主选择的动作标签，并清理回复文本
            clean_response_text, ai_action_tag = parse_action_from_response(response_text)
            
            # 保存对话到历史记录（保存干净的文本，不含[ACTION:xxx]）
            if client_id:
                client_conversation_history[client_id].append({"role": "user", "content": text})
                client_conversation_history[client_id].append({"role": "assistant", "content": clean_response_text})
                
                # 保持历史记录在合理范围（最多保留30条消息）
                if len(client_conversation_history[client_id]) > 30:
                    client_conversation_history[client_id] = client_conversation_history[client_id][-30:]
                print(f"[MEMORY] 对话已保存到 {client_id}（总计 {len(client_conversation_history[client_id])} 条消息）")
            
            # 优先使用AI自主选择的动作，否则关键词兜底
            action_tag = ai_action_tag if ai_action_tag else determine_action_tag(clean_response_text, current_personality)
            
            print(f"[LLM] 通义千问响应：{clean_response_text[:50]}... [动作: {action_tag}, 性格: {current_personality}]")
            return {
                "response_text": clean_response_text,
                "action_tag": action_tag,
                "personality": current_personality
            }
        except Exception as e:
            import traceback
            print(f"[LLM] 处理异常，使用备用响应：{e}")
            print(f"[LLM] 详细错误信息：")
            traceback.print_exc()
            return {
                "response_text": "抱歉，我现在遇到了一些技术问题。",
                "action_tag": "sad",
                "personality": current_personality
            }
    
    # 模拟响应（当USE_REAL_API=False时）
    if image_data:
        return {
            "response_text": "我看到了一张有趣的图片！让我仔细看看。",
            "action_tag": "explain",
            "personality": current_personality
        }
    
    # 基于关键词的模拟纯文本响应
    text_lower = text.lower()
    
    if any(word in text_lower for word in ["hello", "hi", "你好"]):
        return {
            "response_text": "你好！很高兴见到你！",
            "action_tag": "wave",
            "personality": current_personality
        }
    elif any(word in text_lower for word in ["sad", "unhappy", "悲伤"]):
        return {
            "response_text": "听到这个我很难过，有什么我可以帮助的吗？",
            "action_tag": "sad",
            "personality": current_personality
        }
    elif any(word in text_lower for word in ["explain", "tell me", "what is", "解释", "告诉我"]):
        return {
            "response_text": "让我来给你解释一下，这很有趣！",
            "action_tag": "explain",
            "personality": current_personality
        }
    elif any(word in text_lower for word in ["think", "calculate", "compute", "思考", "计算"]):
        return {
            "response_text": "让我想一想...",
            "action_tag": "thinking",
            "personality": current_personality
        }
    else:
        return {
            "response_text": "这很有意思！我很乐意帮助你。",
            "action_tag": "happy",
            "personality": current_personality
        }


# ============================================================
# 使用说明
# ============================================================
# 1. 安装依赖：pip install requests
# 2. 获取API Key：访问 https://dashscope.aliyun.com/ 注册并获取API密钥
# 3. 将API密钥粘贴到上面的 QWEN_API_KEY
# 4. 设置 USE_REAL_API = True 启用真实API调用
# 5. 可选：修改 QWEN_TEXT_MODEL 和 QWEN_VL_MODEL 选择不同的模型


# ============================================================
# 客户端处理器（多线程）
# ============================================================
def handle_client(client_socket, client_address):
    """
    在单独的线程中处理机器人客户端连接
    
    参数：
        client_socket: 客户端的Socket对象
        client_address: 客户端地址元组 (ip, port)    """
    print(f"[SERVER] 新连接来自 {client_address}")
    
    try:
        while True:
            # 接收来自机器人的数据
            data = b''
            while True:
                chunk = client_socket.recv(BUFFER_SIZE)
                if not chunk:
                    print(f"[SERVER] 客户端 {client_address} 已断开连接")
                    return
                data += chunk
                # 检查是否接收到完整的JSON（以换行符结尾）
                if b'\n' in chunk:
                    break
            
            if not data:
                break
            
            # 解码并解析JSON
            try:
                request = json.loads(data.decode('utf-8'))
                
                # 提取字段
                text = request.get('text', '')
                image_data = request.get('image_data', None)
                audio_data = request.get('audio_data', None)
                
                # ============================================================
                # 👤 显示用户输入
                # ============================================================
                print("\n" + "="*30)
                print("👤 [用户输入]")
                print("="*30)
                if audio_data:
                    print(f"🎤 音频: 已提供（{len(audio_data)} 字节）")
                if text:
                    print(f"💬 文本: {text}")
                if image_data:
                    print(f"📷 图像: 已提供（{len(image_data)} 字节）")
                print("="*30 + "\n")
                
                # 生成LLM响应（传递client_address用于性格跟踪）
                llm_response = get_llm_response(text, image_data, audio_data, client_address)
                
                # ============================================================
                # 💬 控制台预览：显示机器人即将说的话
                # ============================================================
                print("\n" + "="*60)
                print("🤖 [机器人回复预览]")
                print("="*60)
                print(f"📝 完整回复: {llm_response['response_text']}")
                print(f"🎭 动作标签: {llm_response['action_tag']}")
                print(f"😊 性格模式: {llm_response.get('personality', 'friendly')}")
                print("="*60 + "\n")
                
                # 准备响应JSON
                response = {
                    "response_text": llm_response["response_text"],
                    "action_tag": llm_response["action_tag"],
                    "personality": llm_response.get("personality", "friendly")
                }
                
                # 将响应发送回机器人
                response_json = json.dumps(response, ensure_ascii=False) + '\n'
                client_socket.sendall(response_json.encode('utf-8'))
                print(f"[SERVER] ✅ 已发送响应到机器人")
                
            except json.JSONDecodeError as e:
                print(f"[SERVER] JSON解码错误：{e}")
                error_response = {
                    "response_text": "抱歉，我没有理解你的意思。",
                    "action_tag": "thinking"
                }
                client_socket.sendall((json.dumps(error_response) + '\n').encode('utf-8'))
            except Exception as e:
                print(f"[SERVER] 处理请求时出错：{e}")
                error_response = {
                    "response_text": "抱歉，出现了一些问题。",
                    "action_tag": "sad"
                }
                client_socket.sendall((json.dumps(error_response) + '\n').encode('utf-8'))
    
    except Exception as e:
        print(f"[SERVER] 连接错误：{e}")
    finally:
        client_socket.close()
        print(f"[SERVER] 连接已关闭：{client_address}")


# ============================================================
# TCP服务器（主函数）
# ============================================================
def start_server():
    """
    启动TCP Socket服务器并监听机器人连接
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((SERVER_HOST, SERVER_PORT))
        server_socket.listen(5)
        print(f"[SERVER] 正在监听 {SERVER_HOST}:{SERVER_PORT}")
        print(f"[SERVER] 等待机器人连接...")
        
        while True:
            # 接受新连接
            client_socket, client_address = server_socket.accept()
            
            # 为每个客户端创建新线程
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address),
                daemon=True
            )
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\n[SERVER] 正在关闭服务器...")
    except Exception as e:
        print(f"[SERVER] 错误：{e}")
    finally:
        server_socket.close()
        print("[SERVER] 服务器已停止")


# ============================================================
# 主入口
# ============================================================
# ============================================================
# 本地语音识别功能
# ============================================================
def record_audio_from_pc(duration=5):
    """
    从电脑麦克风录音
    
    参数：
        duration (int): 录音时长（秒）
    
    返回：
        AudioData: 音频数据对象
    """
    recognizer = sr.Recognizer()
    
    try:
        with sr.Microphone() as source:
            print("\n🎤 [录音] 请说话（录音{}秒）...".format(duration))
            # 调整环境噪音
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            # 录音
            audio = recognizer.listen(source, timeout=duration, phrase_time_limit=duration)
            print("✅ [录音] 录音完成")
            return audio
    except Exception as e:
        print(f"❌ [录音错误] {e}")
        return None


def recognize_speech_from_audio(audio):
    """
    使用Google Speech Recognition识别英文语音
    
    参数：
        audio: AudioData对象
    
    返回：
        str: 识别的文本
    """
    recognizer = sr.Recognizer()
    
    try:
        print("🔄 [识别] 正在识别语音...")
        # 使用Google Speech Recognition（免费，支持英文）
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
        print(f"❌ [识别错误] {e}")
        return None


def interactive_voice_mode():
    """
    交互式语音模式：电脑辅助NAO输入
    电脑负责语音识别，结果发送给NAO执行
    """
    print("\n" + "=" * 60)
    print("🎙️  电脑辅助NAO - 语音输入模式")
    print("=" * 60)
    print("功能：")
    print("  • 电脑麦克风录音 + 语音识别（英文，95%准确率）")
    print("  • 自动检测是否需要视觉功能")
    print("  • 生成NAO指令（文本 + 动作 + 视觉提示）")
    print("\n输入模式：")
    print("  1. 按 [ENTER] 直接回车 → 语音输入（英文）")
    print("  2. 输入文字后回车 → 键盘输入")
    print("  3. 输入 'quit' → 退出")
    print("=" * 60)
    
    # 模拟客户端地址（本地模式）
    local_client = "pc_voice_assistant"
    
    while True:
        try:
            print("\n" + "=" * 60)
            user_input = input("💬 [输入] 请输入文本，或直接按回车使用语音：").strip()
            
            # 退出指令
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 再见！")
                break
            
            # 判断输入模式
            if not user_input:
                # 空输入 → 语音模式
                audio = record_audio_from_pc(duration=5)
                if audio:
                    text = recognize_speech_from_audio(audio)
                    if not text:
                        print("⚠️  语音识别失败，请重试")
                        continue
                else:
                    continue
            else:
                # 有输入 → 键盘模式
                text = user_input
            
            print(f"\n📝 [识别结果] {text}")
            
            # 检查是否需要视觉功能
            needs_vision = any(keyword in text.lower() for keyword in VISION_KEYWORDS)
            
            if needs_vision:
                print("📸 [视觉检测] 检测到视觉关键词！")
                print("⚠️  [提示] 请确保NAO已连接并准备拍照")
                print("    NAO将会自动触发拍照功能")
            
            # 调用大模型获取回复（不带图像，因为图像由NAO提供）
            response = get_llm_response(text, image_data=None, audio_data=None, client_address=local_client)
            
            if response:
                response_text = response.get('response_text', '')
                action_tag = response.get('action_tag', 'greeting')
                personality = response.get('personality', 'friendly')
                
                print("\n" + "=" * 60)
                print("🤖 [NAO指令生成]")
                print("=" * 60)
                print(f"📝 输入文本: {text}")
                if needs_vision:
                    print(f"📸 需要视觉: 是 (检测到关键词)")
                else:
                    print(f"📸 需要视觉: 否")
                print(f"💬 NAO回复: {response_text}")
                print(f"🎭 NAO动作: {action_tag}")
                print(f"😊 性格模式: {personality}")
                print("=" * 60)
                
                # 生成发送给NAO的JSON指令
                nao_command = {
                    "text": text,
                    "needs_vision": needs_vision
                }
                
                print("\n📤 [发送指令] 将以下指令发送给NAO：")
                print(json.dumps(nao_command, indent=2, ensure_ascii=False))
                print("\n💡 [提示] NAO将执行：")
                if needs_vision:
                    print("  1. 接收文本")
                    print("  2. 检测到视觉关键词 → 拍照")
                    print("  3. 发送文本+图像到服务器")
                    print("  4. 接收服务器回复")
                    print("  5. 执行动作 + 说话")
                else:
                    print("  1. 接收文本")
                    print("  2. 发送文本到服务器")
                    print("  3. 接收服务器回复")
                    print("  4. 执行动作 + 说话")
                    
            else:
                print("❌ 大模型无响应")
                
        except KeyboardInterrupt:
            print("\n👋 用户中断，退出")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("=" * 60)
    print("NAO机器人远程大脑服务器")
    print("Python 3.x - 笔记本电脑端")
    print("=" * 60)
    print("\n请选择运行模式：")
    print("  1 - TCP服务器模式（等待NAO连接）")
    print("  2 - 交互式语音模式（本地语音+键盘输入）")
    
    try:
        mode = input("\n请输入模式编号 [1/2]: ").strip()
        
        if mode == "2":
            interactive_voice_mode()
        else:
            # 默认启动TCP服务器
            start_server()
    except KeyboardInterrupt:
        print("\n退出")
