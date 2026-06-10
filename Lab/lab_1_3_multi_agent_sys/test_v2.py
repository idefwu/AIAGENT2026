import requests
import json

# 1. 設定 Open WebUI API 參數
OLLAMA_API_URL = "http://localhost:8080/api/chat/completions"
OPENWEBUI_API_KEY = "sk-1540f219fcb246b9bb55c7951491c01b" 
MODEL_NAME = "gemma4_e4b_ctx_128k_nothink:latest"

def get_api_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENWEBUI_API_KEY}"
    }

# 2. 定義兩個 Agent 的系統提示詞
WRITER_PROMPT = (
    "你是一位專業的故事作家。請根據使用者的主題寫出一篇極短篇小說（100字以內）。"
    "如果收到編輯的修改建議，請優化你的故事並提供更新版本。"
)

EDITOR_PROMPT = (
    "你是一位嚴格的文學編輯。請評估作家的故事，並給出具體的改進建議。"
    "如果故事已經非常完美，請只回覆兩個字：'通過'。請勿包含其他文字。"
)

# 封裝呼叫 API 的函式
def call_llm(messages):
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_API_URL, headers=get_api_headers(), json=payload, timeout=30)
        response.raise_for_status() # 檢查 HTTP 狀態碼
        result = response.json()
        return result['choices'][0]['message']['content'].strip()
    except requests.exceptions.RequestException as e:
        print(f"\n❌ API 呼叫失敗！錯誤訊息: {e}")
        if 'response' in locals() and response:
            print(f"回應內容: {response.text}")
        raise e

def run_multi_agent_system(topic: str, max_turns: int = 3):
    print(f"🎬 任務開始！主題：【{topic}】")
    print(f"🤖 使用模型：{MODEL_NAME}\n" + "="*40)
    
    # 初始化兩個 Agent 的獨立對話紀錄（加入 System Prompt 確立角色）
    writer_messages = [{"role": "system", "content": WRITER_PROMPT}]
    editor_messages = [{"role": "system", "content": EDITOR_PROMPT}]
    
    # 初始輸入：使用者的主題
    current_message = f"請寫一個關於「{topic}」的故事。"
    
    for turn in range(1, max_turns + 1):
        print(f"\n🔄 --- 第 {turn} 輪對話 ---")
        
        # --- 作家 Agent 執行 ---
        writer_messages.append({"role": "user", "content": current_message})
        writer_text = call_llm(writer_messages)
        writer_messages.append({"role": "assistant", "content": writer_text})
        print(f"✍️ 【作家 Agent】:\n{writer_text}")
        
        # --- 編輯 Agent 執行 ---
        editor_messages.append({"role": "user", "content": writer_text})
        editor_text = call_llm(editor_messages)
        editor_messages.append({"role": "assistant", "content": editor_text})
        print(f"🧐 【編輯 Agent】:\n{editor_text}")
        
        # --- 檢查終止條件 ---
        if "通過" in editor_text:
            print("\n🎉 【系統】編輯已審查通過，任務圓滿結束！")
            break
            
        # 將編輯的建議作為作家下一輪的輸入
        current_message = f"這是編輯給你的修改建議：'{editor_text}'。請根據建議修改故事。"
    else:
        print("\n⚠️ 【系統】達到最大對話輪數，協作結束。")

# 3. 執行系統
if __name__ == "__main__":
    run_multi_agent_system(topic="會飛的貓咪", max_turns=3)
