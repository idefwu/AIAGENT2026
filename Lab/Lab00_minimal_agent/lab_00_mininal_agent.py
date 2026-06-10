import json
import os
import subprocess
from pathlib import Path

from openai import OpenAI


# ============================================================
# Open WebUI + Ollama
# ============================================================

client = OpenAI(
    #base_url="http://172.10.0.2:8080/api/v1",
    base_url="http://localhost:8080/api/v1",
    api_key="sk-1540f219fcb246b9bb55c7951491c01b"
)

MODEL = "gemma4_e4b_ctx_128k_nothink:latest"   # change to your Ollama model


# ============================================================
# Tool definitions (visible to LLM)
# ============================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path.",
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
            "description": "Read the contents of a file.",
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
            "description": "Write content to a file, overwriting if it exists.",
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
            "description": "Run a whitelisted shell command and return its output.",
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
# Tool implementations
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
        return Path(path_str).read_text(
            encoding="utf-8",
            errors="ignore"
        )
    except Exception as e:
        return f"Error: {e}"


def write_file(path_str: str, content: str) -> str:
    try:
        Path(path_str).write_text(
            content,
            encoding="utf-8"
        )
        return f"Written: {path_str}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================
# Command permissions
# ============================================================

AUTO_COMMANDS = {
    "ls",
    "cat",
    "echo",
    "node",
    "rg"
}

CONFIRM_COMMANDS = {
    "npm"
}


def ask_permission(question: str) -> bool:
    answer = input(question).strip().lower()
    return answer == "y"


def run_command(command: str) -> str:
    binary = command.strip().split()[0]

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
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return result.stdout

        return result.stderr

    except Exception as e:
        return str(e)


# ============================================================
# Tool dispatcher
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
# AGENTS.md memory
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

        return [
            {
                "role": "system",
                "content": rules
            }
        ]

    except Exception:
        return []


# ============================================================
# Agent loop
# ============================================================

def run_agent(task: str):

    messages = [
        *load_memory(),
        {
            "role": "user",
            "content": task
        }
    ]

    print(f"user: {task}")

    for step in range(5):

        print(f"\n── step {step + 1}")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
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
        # Tool call
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

            raw = run_tool(
                tool_name,
                args
            )

            observation = (
                raw[:2000] + "\n[...truncated]"
                if len(raw) > 2000
                else raw
            )

            print(
                f"observation:\n"
                f"{observation}"
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": observation
                }
            )

            continue

        # ----------------------------------------------------
        # Final response
        # ----------------------------------------------------
        content = message.content or ""

        # remove DeepSeek/Qwen thinking tags
        import re

        content = re.sub(
            r"<think>[\s\S]*?</think>",
            "",
            content
        ).strip()

        print(f"model: {content}")
        return

    print("Stopped: step limit reached.")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":

    task = (
        "Read package.json, then write a short but complete "
        "project summary to summary.txt, in zhtw and en. "
    )

    run_agent(task)

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
        
    task2 = (
        "Read lab_00_mininal_agent.py file, then write a short but complete "
        "project summary to summary2.txt, in zhtw and en. "
    )

    run_agent(task2)

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