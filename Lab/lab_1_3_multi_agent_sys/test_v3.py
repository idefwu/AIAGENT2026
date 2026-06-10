import requests
import json
import re

# 1. 設定 API 參數
OLLAMA_API_URL = "http://localhost:8080/api/chat/completions"
OPENWEBUI_API_KEY = "sk-1540f219fcb246b9bb55c7951491c01b" 

# 定義兩個不同的模型名稱
MODEL_WORKER = "gemma4_e4b_ctx_128k_nothink:latest"    # 作家與編輯
MODEL_AUDIENCE = "gemma4_e2b_nothink:latest"  # 觀眾評審（使用更強大的模型）
#MODEL_AUDIENCE = "gemma4_e4b_ctx_128k_nothink:latest"  # 觀眾評審（使用更強大的模型）

def get_api_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENWEBUI_API_KEY}"
    }

# 2. 定義系統提示詞
WRITER_PROMPT = (
    "你是一位專業的故事作家。請根據使用者的主題寫出一篇極短篇小說（300字左右）。"
    "如果收到編輯的建議，請吸取教訓並重寫優化你的故事。"
)

EDITOR_PROMPT = (
    "你是一位嚴格的文學編輯。請閱讀作家的故事，並給出1到2句具體、一針見血的修改建議，"
    "特別專注在如何加強起承轉合與故事賣點。"
)

AUDIENCE_PROMPT = (
    "你是一位挑剔的小說讀者。請針對作家最新版的故事進行嚴格評分（給出1-10分）。"
    "你必須嚴格按照以下格式回覆，不要包含任何額外的廢話、聊天或解釋：\n"
    "1. 故事完整: [分數]\n"
    "2. 有足夠且合適的起承轉合: [分數]\n"
    "3. 有賣點: [分數]\n"
    "4. 文句流暢白話易懂: [分數]\n"
    "原因: [簡短的一句評語]"
)

# 呼叫 API 函式 (新增 model_name 參數)
def call_llm(messages, model_name):
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.3,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_API_URL, headers=get_api_headers(), json=payload, timeout=240)
        response.raise_for_status()
        result = response.json()
        
        # 修正點：加入 [0] 取得陣列的第一個元素，並加入安全防錯 get()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content'].strip()
        
        # 備用方案：某些 Open WebUI/Ollama 版本可能會直接把 message 放在最外層
        elif 'message' in result:
            return result['message']['content'].strip()
            
        else:
            print(f"⚠️ 無法解析的回應結構: {result}")
            raise KeyError("找不到 content 欄位")
            
    except requests.exceptions.RequestException as e:
        print(f"\n❌ API 呼叫失敗！錯誤訊息: {e}")
        raise e


def call_llma(messages, model_name):
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2, # 降低隨機性，讓評分更客觀
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_API_URL, headers=get_api_headers(), json=payload, timeout=240)
        response.raise_for_status()
        result = response.json()
        return result['choices']['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        print(f"\n❌ API 呼叫失敗！錯誤訊息: {e}")
        raise e

# 解析觀眾分數的工具函式
def parse_audience_scores(text):
    # 使用正規表達式抓取 1. 到 4. 的分數
    scores = re.findall(r'\d\.\s*[^:]+:\s*([0-9.]+)', text)
    if len(scores) == 4:
        try:
            return [float(s) for s in scores]
        except ValueError:
            return [0.0, 0.0, 0.0, 0.0]
    return [0.0, 0.0, 0.0, 0.0]

def run_multi_agent_system(topic: str, max_turns: int = 10):
    print(f"🎬 任務開始！主題：【{topic}】")
    print(f"🧱 協作群：作家/編輯 ({MODEL_WORKER}) ➔ 監審觀眾 ({MODEL_AUDIENCE})")
    print(f"🚨 安全天花板上限：{max_turns} 輪\n" + "="*50)
    
    writer_messages = [{"role": "system", "content": WRITER_PROMPT}]
    editor_messages = [{"role": "system", "content": EDITOR_PROMPT}]
    
    current_message = f"請寫一個關於「{topic}」的故事。"
    latest_story = ""
    
    for turn in range(1, max_turns + 1):
        print(f"\n🔄 =======【 第 {turn} / {max_turns} 輪 協作修訂 】=======")
        
        # --- 1. 作家 Agent 寫作 ---
        writer_messages.append({"role": "user", "content": current_message})
        latest_story = call_llm(writer_messages, MODEL_WORKER)
        writer_messages.append({"role": "assistant", "content": latest_story})
        print(f"✍️ 【作家 Agent】:\n{latest_story}\n" + "-"*30)
        
        # --- 2. 觀眾 Agent 評分 (獨立環境，每次只看最新故事) ---
        audience_messages = [
            {"role": "system", "content": AUDIENCE_PROMPT},
            {"role": "user", "content": f"請評估這個故事：\n{latest_story}"}
        ]
        audience_review = call_llm(audience_messages, MODEL_AUDIENCE)
        print(f"👀 【觀眾 Agent 評分結果】:\n{audience_review}")
        
        # 計算平均分
        scores = parse_audience_scores(audience_review)
        avg_score = sum(scores) / 4 if scores else 0
        print(f"📊 當前總平均分：{avg_score:.2f} / 10 (通過門檻：8.50)")
        
        # --- 3. 檢查觀眾是否滿意 (提前終止條件) ---
        if avg_score >= 8.5:
            print(f"\n🎉 【系統】太棒了！觀眾平均打出了 {avg_score:.2f} 的高分，達到 8.5 門檻，任務圓滿結束！")
            break
            
        # --- 4. 沒通過，交給編輯 Agent 給予毒舌建議 ---
        editor_messages.append({"role": "user", "content": f"這是作家寫的最新故事：\n{latest_story}\n\n觀眾只給了平均 {avg_score:.2f} 分，請給出修改建議。"})
        editor_advice = call_llm(editor_messages, MODEL_WORKER)
        editor_messages.append({"role": "assistant", "content": editor_advice})
        print(f"-"*30 + f"\n🧐 【編輯 Agent 修改意見】:\n{editor_advice}")
        
        # 將編輯與觀眾的反饋結合，作為作家下一輪的輸入
        current_message = f"編輯建議：'{editor_advice}'。請參考這個建議大幅度優化故事，目標是滿足觀眾的口味。"
        
    else:
        print(f"\n⚠️ 【系統】已達到天花板上限 {max_turns} 輪。雖然分數未達標，但為了防止死循環，協作強制結束。")

# 3. 執行系統
if __name__ == "__main__":
    run_multi_agent_system(topic="秘密基地裡的時空發電機", max_turns=10)
