import csv
import sys
import json
import requests
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

QUESTION_BANK = [
    "請用繁體中文寫一篇關於人工智慧未來發展的 100 字短評。",
    "計算一下 1234 乘以 5678 等於多少？並給出簡單的驗證步驟。",
    "請推薦三個台灣適合三天兩夜旅遊的私房景點，並說明原因。",
    "什麼是 RESTful API？請用極度通俗、連小學生都能聽懂的比喻來解釋它。",
    "請寫一封給合作夥伴的商業感謝信，語氣要專業且客氣，大約 150 字。",
    "請幫我列出五個提高工作效率的時間管理技巧。"
]

print_lock = threading.Lock()
global_results = []

def test_single_user_stream(user_info):
    base_url = "http://192.168.1.191:8080/api/chat/completions"
    model_name = "gemma4:e4b"
    
    name = user_info.get('name', '未知')
    apikey = user_info.get('apikey', '').strip()
    
    if not apikey:
        return []

    user_questions = random.sample(QUESTION_BANK, k=4)
    user_records = []
    user_total_start = time.time()
    
    headers = {
        "Authorization": f"Bearer {apikey}",
        "Content-Type": "application/json"
    }

    for i, q in enumerate(user_questions, start=1):
        q_start = time.time()
        ttft = 0.0          # 首字響應時間
        total_time = 0.0    # 總花費時間
        status = "成功"
        error_msg = ""
        
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": q}],
            "temperature": 0.7,
            "stream": True  # 啟用串流模式，避免大文本卡死
        }
        
        try:
            # 壓測佇列很長，將超時拉長到 600 秒（10分鐘）
            response = requests.post(base_url, headers=headers, json=payload, timeout=600, stream=True)
            
            if response.status_code == 200:
                first_token_received = False
                
                # 讀取串流
                for line in response.iter_lines():
                    if line:
                        # 收到第一個 token，紀錄首字時間（排隊時間）
                        if not first_token_received:
                            ttft = round(time.time() - q_start, 2)
                            first_token_received = True
                
                q_end = time.time()
                total_time = round(q_end - q_start, 2)
            else:
                status = "失敗"
                error_msg = f"HTTP {response.status_code}"
                total_time = round(time.time() - q_start, 2)
        except Exception as e:
            status = "異常"
            error_msg = str(e)[:30]
            total_time = round(time.time() - q_start, 2)
            
        record = {
            "name": name,
            "question_num": f"Q{i}",
            "ttft": ttft,               # 首字時間
            "duration": total_time,     # 全程時間
            "status": status,
            "error": error_msg
        }
        user_records.append(record)
        
        with print_lock:
            print(f"⚡ [進度] 使用者: {name:<8} | 題 {i}/4 | 排隊首字: {ttft:>5}秒 | 總耗時: {total_time:>5}秒 | 狀態: {status}")

    user_total_end = time.time()
    total_duration = round(user_total_end - user_total_start, 2)
    
    valid_durations = [r['duration'] for r in user_records if r['status'] == "成功"]
    avg_duration = round(sum(valid_durations) / len(valid_durations), 2) if valid_durations else 0.0

    for r in user_records:
        r["total_duration"] = total_duration
        r["avg_duration"] = avg_duration

    return user_records

def run_stress_test(csv_file_path):
    global global_results
    users_list = []
    
    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                users_list.append(row)
    except FileNotFoundError:
        print(f"❌ 錯誤：找不到檔案 '{csv_file_path}'。")
        return

    num_users = len(users_list)
    print(f"==========================================================================")
    print(f" 🔥 正在對 Ollama 發動 🚀 串流併發壓力測試 (延長超時至 10 分鐘)")
    print(f" 👥 壓測人數: {num_users} 人 | 總請求數: {num_users * 4} 次")
    print(f"==========================================================================")

    start_wall_time = time.time()
    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures = {executor.submit(test_single_user_stream, user): user for user in users_list}
        for future in as_completed(futures):
            res = future.result()
            if res:
                global_results.extend(res)

    total_wall_duration = round(time.time() - start_wall_time, 2)
    print_summary_report(total_wall_duration)

def print_summary_report(total_wall_duration):
    print(f"\n==========================================================================")
    print(f" 📊 串流壓力測試最終統計報告")
    print(f"==========================================================================")
    print(f" ⏱️ 伺服器總承載時間: {total_wall_duration} 秒")
    
    user_summary = {}
    for r in global_results:
        name = r['name']
        if name not in user_summary:
            user_summary[name] = {"total": r['total_duration'], "avg": r['avg_duration'], "details": [], "success": 0, "failed": 0}
        
        # 顯示格式：Q1(首字秒數/總秒數)
        user_summary[name]["details"].append(f"{r['question_num']}({r['ttft']}s/{r['duration']}s)")
        if r['status'] == "成功":
            user_summary[name]["success"] += 1
        else:
            user_summary[name]["failed"] += 1

    print("\n【各使用者花費明細 (格式: 問題(排隊首字時間 / 總生成時間))】:")
    print(f"{'使用者':<10} | {'各題花費明細 (TTFT / Total)':<45} | {'全程總時間':<10} | {'成功/失敗':<10} | {'平均時間':<10}")
    print("-" * 95)
    
    for name, data in user_summary.items():
        details_str = ", ".join(data["details"][:2]) + "..." # 終端機寬度排版，僅抓前段
        status_ratio = f"{data['success']}/{data['failed']}"
        print(f"{name:<12} | {details_str:<45} | {data['total']:>8} 秒 | {status_ratio:^9} | {data['avg']:>8} 秒")
    print(f"==========================================================================")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    run_stress_test(sys.argv[1])
