import csv
import sys
import json
import requests
import time

def test_batch_users(csv_file_path):
    base_url = "http://192.168.1.191:8080/api/chat/completions"
    model_name = "gemma4:e4b"
    
    # 用於統計結果的計數器與清單
    total_users = 0
    success_count = 0
    failed_users = []
    
    print(f"==========================================================================")
    print(f" 🚀 開始批次測試 Open WebUI 使用者連線")
    print(f" 檔案來源: {csv_file_path}")
    print(f" 測試模型: {model_name}")
    print(f"==========================================================================")
    
    try:
        with open(csv_file_path, mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            # 檢查必要欄位
            required_columns = {'name', 'email', 'password', 'role', 'apikey'}
            if not required_columns.issubset(csv_reader.fieldnames):
                print(f"❌ 錯誤：CSV 檔案缺少必要欄位！必須包含: {required_columns}")
                return
            
            # 使用迴圈跑遍 CSV 內的所有使用者
            for row in csv_reader:
                total_users += 1
                name = row.get('name', '未命名')
                role = row.get('role', '無角色')
                apikey = row.get('apikey', '').strip()
                
                print(f"\n[{total_users}] 正在測試使用者: {name} (角色: {role})...")
                
                # 檢查該列是否有 API Key
                if not apikey:
                    print(f" ⚠️ 跳過：此使用者沒有填寫 apikey 欄位。")
                    failed_users.append({"name": name, "reason": "無 API Key"})
                    continue
                
                headers = {
                    "Authorization": f"Bearer {apikey}",
                    "Content-Type": "application/json"
                }
                
                prompt_message = f"你好，我是使用者 {name}，角色是 {role}。請用繁體中文簡短回應我：『連線成功』。"
                
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt_message}],
                    "temperature": 0.5
                }
                
                try:
                    # 發送請求，設定 15 秒超時防止程式卡死
                    response = requests.post(base_url, headers=headers, json=payload, timeout=15)
                    
                    if response.status_code == 200:
                        result_json = response.json()
                        
                        # 解析模型回傳文字
                        if 'choices' in result_json and isinstance(result_json['choices'], list):
                            ai_response = result_json['choices'][0]['message']['content'].strip()
                        elif 'message' in result_json and 'content' in result_json['message']:
                            ai_response = result_json['message']['content'].strip()
                        else:
                            ai_response = "(成功連線，但回傳格式非預期)"
                        
                        print(f" ✅ 測試成功！模型回應: {ai_response}")
                        success_count += 1
                    else:
                        print(f" ❌ 測試失敗！伺服器狀態碼: {response.status_code}")
                        failed_users.append({"name": name, "reason": f"狀態碼 {response.status_code} ({response.text[:50]})"})
                        
                except requests.exceptions.RequestException as req_err:
                    print(f" ❌ 連線異常: {req_err}")
                    failed_users.append({"name": name, "reason": "網路連線或超時錯誤"})
                
                # 稍微停頓 0.2 秒，避免瞬間衝擊伺服器 API
                time.sleep(0.2)
                
        # ==================== 印出最終統計報告 ====================
        print(f"\n==========================================================================")
        print(f" 📊 批次測試結束統計報告")
        print(f"==========================================================================")
        print(f" 🔹 總計讀取人數 : {total_users} 位")
        print(f" 🔹 測試成功人數 : {success_count} 位")
        print(f" 🔹 測試失敗人數 : {len(failed_users)} 位")
        
        if failed_users:
            print(f"\n ❌ 失敗名單詳情 :")
            for f in failed_users:
                print(f"   - 使用者: {f['name']} | 原因: {f['reason']}")
        else:
            print(f"\n 🎉 太棒了！名單內的所有使用者皆能正常存取 Open WebUI！")
        print(f"==========================================================================")

    except FileNotFoundError:
        print(f"❌ 錯誤：找不到檔案 '{csv_file_path}'。")
    except Exception as e:
        print(f"❌ 發生預期之外的錯誤: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法：python test_batch.py user.csv")
        sys.exit(1)
        
    test_batch_users(sys.argv[1])
