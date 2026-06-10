import json
import os
import subprocess
from pathlib import Path
from openai import OpenAI
# ============================================================
# 🎯 環境設置與模型初始化 (Setup & Initialization)
# 說明：這是 Agent 要使用的「大腦」和「外部介面」。
# client: 設定了要連線的 LLM API 端點。
# MODEL: 指定了用來思考和決策的模型名稱。
# ============================================================
client = OpenAI(
    #base_url="http://172.10.0.2:8080/api/v1",
    base_url="http://localhost:8080/api/v1",
    api_key="sk-1540f219fcb246b9bb55c7951491c01b"
)
MODEL = "gemma4_e4b_ctx_128k_nothink:latest"   # change to your Ollama model

# ============================================================
# 🛠️ 工具定義 (Tool Definitions - LLM 的「能力清單」)
# 說明：這是用標準格式（JSON Schema）告訴 LLM：「我具備哪些外部工具，以及每個工具需要什麼輸入」。
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. (用於查看目錄內容)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. (用於讀取文件內容)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file, overwriting if it exists. (用於改變環境，寫入新資訊)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to write."
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a whitelisted shell command and return its output. (通用系統命令執行)",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run."
                    }
                },
                "required": ["command"]
            }
        }
    }
]

# ============================================================
# 💻 工具實作 (Tool Implementations - Agent 的「實際手臂和腳步」)
# 說明：這裡的函數體，就是真正執行操作的程式碼邏輯。它接收 LLM 傳來的參數，並與作業系統互動。
# ============================================================
def list_files(path_str: str) -> str:
    p = Path(path_str)
    if not p.exists():
        return f"Error: Path does not exist: {path_str}"
    output = []
    for item in p.iterdir():
        if item.is_dir():
            output.append(f"{item.name}/")
        else:
            output.append(item.name)
    return "\n".join(output)

def read_file(path_str: str) -> str:
    try:
        # 核心功能：將檔案的文字內容「讀取」出來，這是 Agent 的「觀察源」。
        return Path(path_str).read_text(
            encoding="utf-8",
            errors="ignore"
        )
    except Exception as e:
        return f"Error: {e}"

def write_file(path_str: str, content: str) -> str:
    try:
        # 核心功能：將文字內容「寫入」檔案，這是 Agent 對環境的「修改」。
        Path(path_str).write_text(
            content,
            encoding="utf-8"
        )
        return f"Written: {path_str}"
    except Exception as e:
        return f"Error: {e}"

# ============================================================
# 🛡️ 命令權限控制 (Command Permissions - 安全機制)
# ============================================================
def ask_permission(question: str) -> bool:
    answer = input(question).strip().lower()
    return answer == "y"

def run_command(command: str) -> str:
    binary = command.strip().split()[0]
    # 這裡實作了「白名單 (Whitelisting)」和「使用者確認」的安全檢查。
    if (
        binary not in AUTO_COMMANDS
        and binary not in CONFIRM_COMMANDS
    ):
        return f"Error: '{binary}' is not an allowed command."
    if binary in CONFIRM_COMMANDS:
        approved = ask_permission(
            f"Allow: {command}? (y/n) "
        )
        if not approved:
            return "User denied the command."
    try:
        # 實際執行系統命令，並捕捉標準輸出（stdout）作為觀察結果。
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout # 返回成功執行的「觀察結果」
        return result.stderr # 如果失敗，返回錯誤訊息作為「觀察結果」
    except Exception as e:
        return str(e)

# ============================================================
# 🔄 工具調度器 (Tool Dispatcher - 中間協調層)
# 說明：這個函數是個「分派工單的櫃台」。它根據 LLM 說要用哪個工具，實際呼叫對應的 Python 函數。
# ============================================================
def run_tool(name: str, args: dict) -> str:
    if name == "list_files":
        return list_files(args["path"])
    if name == "read_file":
        return read_file(args["path"])
    if name == "write_file":
        return write_file(
            args["path"],
            args["content"]
        )
    if name == "run_command":
        return run_command(args["command"])
    return f"Unknown tool: {name}"

# ============================================================
# 🧠 記憶體管理 (Memory Loading - 提供長期背景知識)
# 說明：這裡從外部檔案載入「系統提示/規則」，作為 Agent 的初始「心智模型」。
# ============================================================
def load_memory():
    agents_file = Path("AGENTS.md")
    if not agents_file.exists():
        return []
    try:
        rules = agents_file.read_text(
            encoding="utf-8",
            errors="ignore"
        )
        # 將載入的規則格式化為 LLM 接受的 "system message"。
        return [
            {
                "role": "system",
                "content": rules
            }
        ]
    except Exception:
        return []

# ============================================================
# 🚀 Agent 主循環 (The Main Agent Loop - 核心邏輯)
# 說明：這是整個 Agent 的「運行心跳」。它不斷重複以下步驟，直到任務完成或達到步數上限。
# ============================================================
def run_agent(task: str):
    messages = [
        *load_memory(), # 1. 初始化：加入系統記憶 (System Memory)
        {
            "role": "user",
            "content": task # 2. 輸入：接收用戶的當前任務 (User Input)
        }
    ]
    print(f"user: {task}")

    # 設定最大循環次數，防止無限迴圈。這是 Agent 的「安全機制」。
    for step in range(5):
        print(f"\n── step {step + 1}")
        # (步驟 A) LLM 推理：將歷史對話和工具清單都送給模型，讓它決定下一步要做什麼。
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS, # 必須把工具定義傳入！
            tool_choice="auto"
        )
        message = response.choices[0].message
        print(response.choices[0].finish_reason)
        print(message.tool_calls)
        messages.append(
            message.model_dump(
                exclude_none=True
            )
        )

        # ----------------------------------------------------
        # (步驟 B) Tool Call 處理：如果 LLM 決定要使用工具
        # ----------------------------------------------------
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            tool_name = tool_call.function.name
            args = json.loads(
                tool_call.function.arguments
            )
            print(
                f"tool: {tool_name}"
                f"({json.dumps(args)})"
            )
            # 執行工具，並取得回傳的原始結果 (raw)。
            raw = run_tool(
                tool_name,
                args
            )
            
            # 將長度超過 2000 的內容截斷，確保後續訊息流不會過大。
            observation = (
                raw[:2000] + "\n[...truncated]"
                if len(raw) > 2000
                else raw
            )
            print(
                f"observation:\n"
                f"{observation}"
            )
            # 最關鍵的步驟：將「工具的執行結果 (Observation)」作為一個新的訊息，加入對話紀錄。
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": observation # 這是觀察到的事實！
                }
            )
            continue # 必須跳回 for 迴圈開始，讓 LLM 用這個「新資訊」再次思考。

        # ----------------------------------------------------
        # (步驟 C) Final Response：如果模型判斷沒有工具需要用（即已經可以回答了）
        # ----------------------------------------------------
        content = message.content or ""
        # 清除 LLM 在思考過程中產生的內部標籤，讓輸出更乾淨。
        import re
        content = re.sub(
            r"<think>[\s\S]*?</think>",
            "",
            content
        ).strip()
        print(f"model: {content}") # 最終答案呈現在這裡
        return
    print("Stopped: step limit reached.")

# ============================================================
# ▶️ 主程式運行區 (Main Execution)
# ============================================================
if __name__ == "__main__":
    # --- 第一個任務：演示讀取和寫入 ---
    task = (
        "Read package.json, then write a short but complete "
        "project summary to summary.txt, in zhtw and en. "
    )
    run_agent(task) # 啟動 Agent 循環
    summary_file = Path("summary.txt")
    ok = (
        summary_file.exists()
        and summary_file.read_text(
            encoding="utf-8"
        ).strip()
    )
    if ok:
        print(
            "\nValidation passed: "
            "summary.txt written."
        )
    else:
        print(
            "\nValidation failed: "
            "summary.txt missing or empty."
        )

    print(
        "\n============================================= "
    )

    # --- 第二個任務：演示重新執行 Agent 循環 ---
    task2 = (
        "Read lab_00_mininal_agent.py file, then write a short but complete "
        "project summary to summary2.txt, in zhtw and en. "
    )
    run_agent(task2) # 再次啟動 Agent 循環，測試連續操作能力
    summary_file2 = Path("summary2.txt")
    ok2 = (
        summary_file2.exists()
        and summary_file2.read_text(
            encoding="utf-8"
        ).strip()
    )
    if ok2:
        print(
            "\nValidation passed: "
            "summary2.txt written."
        )
    else:
        print(
            "\nValidation failed: "
            "summary2.txt missing or empty."
        )