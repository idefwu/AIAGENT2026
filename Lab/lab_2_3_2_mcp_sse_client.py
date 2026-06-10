# lab_2_3_mcp_sse_client.py
import json
import requests
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

# 執行方式：先開一個視窗執行伺服器：python mcp_sse_server.py（放著讓它跑）。
#           再開另一個視窗執行客戶端：python lab_2_3_2_mcp_sse_client.py。


OLLAMA_BASE_URL = "http://localhost:8080/"
API_KEY = "sk-1540f219fcb246b9bb55c7951491c01b" 
MODEL = "gemma4_e4b_ctx_128k_nothink:latest"
# MCP Server 的 SSE 連接端點
MCP_SSE_URL = "http://localhost:8000/sse"

def call_llm(messages: list, tools=None):
    payload = {"model": MODEL, "messages": messages, "temperature": 0.1}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat/completions", json=payload, headers={"Authorization": f"Bearer {API_KEY}"})
    return resp.json()

async def main():
    print("=== MCP SSE 檔案讀取 Agent 啟動 ===")
    user_query = input("請輸入問題（例如：分析 mcp.txt）：\n")

    # 透過 網路/SSE 連接遠端的 MCP 伺服器
    async with sse_client(url=MCP_SSE_URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            mcp_tools = await session.list_tools()

            openai_tools = []
            for t in mcp_tools.tools:
                openai_tools.append({
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.inputSchema
                })

            messages = [
                {"role": "system", "content": "你是一個具有本地檔案讀取能力的 AI 助手。請善用工具回答。"},
                {"role": "user", "content": user_query}
            ]

            response = call_llm(messages, openai_tools)
            message = response["choices"][0]["message"]

            if "tool_calls" in message and message["tool_calls"]:
                print("\n[Agent] LLM 決定呼叫遠端 MCP 工具...")
                messages.append(message)

                for tool_call in message["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    args = json.loads(tool_call["function"]["arguments"])
                    filepath = args.get("filepath") or args.get("file_path") or args.get("file_name")

                    print(f"[Agent] 正在透過 SSE 請求工具: {tool_name}, 參數: {filepath}")
                    
                    # 呼叫遠端工具
                    mcp_result = await session.call_tool(tool_name, arguments={"filepath": filepath})
                    result_text = mcp_result.content[0].text if mcp_result.content else ""

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id", "call_123"),
                        "name": tool_name,
                        "content": json.dumps({"content": result_text}, ensure_ascii=False)
                    })

                final_response = call_llm(messages, openai_tools)
                print("\n=== LLM 最終回應 ===")
                print(final_response["choices"][0]["message"]["content"])
            else:
                print("\n=== LLM 回應 ===")
                print(message["content"])

if __name__ == "__main__":
    asyncio.run(main())
