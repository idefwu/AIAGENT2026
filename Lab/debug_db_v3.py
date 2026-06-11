# 覆蓋全新的 debug_db.py
import chromadb

chroma_client = chromadb.PersistentClient(path="./my_vector_db")
collection = chroma_client.get_collection(name="my_rag_collection")

# 獲取資料庫「真正」的總數量
real_count = collection.count()
print(f"📊 目前資料庫底層真正的總總筆數: {real_count}")
print("-" * 60)

TARGET_KEYWORD = "Liquid Neural Networks"

# 讓 Chroma DB 自己在後台做全文檢索搜尋這個關鍵字
search_results = collection.get(
    where_document={"$contains": TARGET_KEYWORD}
)

if search_results['ids']:
    print(f"🎯 【大發現！】原生查詢成功找到 {len(search_results['ids'])} 筆相關資料！")
    for i, cid in enumerate(search_results['ids']):
        print(f"[{i+1}] ID: {cid}")
        print(f"📝 內容: {search_results['documents'][i][:100]}...")
else:
    print(f"❌ 完蛋了！整個資料庫底層的 {real_count} 筆資料裡，真的『完全沒有』包含「{TARGET_KEYWORD}」的區塊。")
    print("👉 結論：請立刻執行上一步修改後的 app.py，重新上傳檔案，文字絕對被剛才的指標陷阱漏掉了。")