import requests
import json
import re

# ================== 配置 ==================
#API_BASE = "http://localhost:8080"   # 你的 OpenWebUI 端口

SERVER_URL = "http://localhost:8080"
# 修正為標準的 Open WebUI / OpenAI 相容路徑
API_BASE = f"{SERVER_URL}/api/v1/chat/completions"

API_KEY = "sk-1540f219fcb246b9bb55c7951491c01b" 
MODEL = "gemma4_e4b_ctx_128k_nothink:latest"
#MODEL = "gemma4:e4b"

#SERVER_URL = "http://localhost:8080"
#API_BASE = f"{SERVER_URL}/api/chat/completions"



HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ================== 工具定義 ==================
def weather_tool(city: str) -> str:
    """模擬天氣工具（實際上你可以接真實 API）"""
    # 這裡示範固定回傳，實際可替換成真實天氣 API
    return "30°C, cloudy, with afternoon thunderstorms."

# ================== 呼叫 LLM ==================
def call_llm(prompt: str, temperature=0.7) -> str:
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": 1024
    }
    
    response = requests.post(
        API_BASE, 
        json=payload, 
        headers=HEADERS
    )
    
    if response.status_code != 200:
        raise Exception(f"API Error: {response.text}")
    
    return response.json()["choices"][0]["message"]["content"]

# ================== ReAct 主循環 ==================
def react_agent(query: str, max_steps=10):
    print(f"👤 User: {query}\n")
    
    history = f"Question: {query}\n"
    
    for step in range(1, max_steps + 1):
        print(f"--- Step {step} ---")
        
        # 1. Thought + Action
        prompt = f"""{history}

You are a helpful assistant using ReAct (Reasoning + Acting) method.
Think step by step and respond in the following format:

Thought: [your reasoning]
Action: [tool name] [input]   # e.g. Weather Taipei

Answer only with Thought and Action (if needed)."""

        response = call_llm(prompt)
        print(f"🤖 LLM:\n{response}\n")
        
        history += f"\n{response}"
        
        # 2. 解析 Action
        action_match = re.search(r"Action:\s*(.+)", response, re.IGNORECASE)
        
        if not action_match:
            # 可能直接給最終答案
            final_match = re.search(r"Final Answer:?\s*(.+)", response, re.IGNORECASE | re.DOTALL)
            if final_match:
                print(f"✅ Final Answer: {final_match.group(1).strip()}")
                return
            continue
        
        action_text = action_match.group(1).strip()
        
        # 3. 執行工具（目前只支援 weather）
        if "weather" in action_text.lower() or "台北" in action_text or "Taipei" in action_text:
            city = "Taipei"
            observation = weather_tool(city)
            obs_text = f"Observation: {observation}"
            print(f"🔧 Tool: {obs_text}\n")
            history += f"\n{obs_text}"
        else:
            print("⚠️ Unknown tool, continuing...\n")
    
    print("⚠️ Reached max steps")

# ================== 執行 ==================
if __name__ == "__main__":
    query = "Is it a good day for running in Taipei today?"
    react_agent(query)