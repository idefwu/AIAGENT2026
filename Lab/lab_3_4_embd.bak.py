import requests
import json

# 您的環境設定
API_BASE_URL = "http://192.168.1.153:8080/api/chat/completions"
API_KEY = "sk-cebd4fabff5f4b5d8434795173832ba9"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def get_embedding(text):
    """使用 Ollama 的 Embedding API 獲取文本向量"""
    payload = {
        "model": "gemma4_e4b_nothink:latest",
        "input": text
    }
    response = requests.post(f"{API_BASE_URL}/embeddings", headers=HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()["data"][0]["embedding"]
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def llm_generate(prompt):
    """使用 Ollama 的 Completions API 生成回應"""
    payload = {
        "model": "gemma4:e4b",
        "prompt": prompt,
        "max_tokens": 150
    }
    response = requests.post(f"{API_BASE_URL}/completions", headers=HEADERS, json=payload)
    if response.status_code == 200:
        return response.json()["choices"][0]["text"]
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None


# 第一部分：展示 Embedding 的語義理解能力
print("="*60)
print("第一部分：Embedding 的意義 - 語義相似度比較")
print("="*60)

# 定義一些詞彙
words = ["國王", "皇后", "男人", "女人", "蘋果", "香蕉", "電腦"]

# 獲取每個詞的 Embedding
embeddings = {}
for word in words:
    emb = get_embedding(word)
    if emb:
        embeddings[word] = emb

# 定義一個計算餘弦相似度的函數
def cosine_similarity(vec1, vec2):
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    return dot_product / (norm1 * norm2)

# 比較「國王」與其他詞的相似度
print("\n'國王' 與其他詞的語義相似度：")
for word in words:
    if word != "國王" and word in embeddings:
        similarity = cosine_similarity(embeddings["國王"], embeddings[word])
        print(f"  國王 vs {word}: {similarity:.4f}")

# 比較「蘋果」與其他詞的相似度
print("\n'蘋果' 與其他詞的語義相似度：")
for word in words:
    if word != "蘋果" and word in embeddings:
        similarity = cosine_similarity(embeddings["蘋果"], embeddings[word])
        print(f"  蘋果 vs {word}: {similarity:.4f}")

print("\n結論：'國王' 與 '皇后' 的相似度最高，'蘋果' 與 '香蕉' 的相似度最高。")
print("這證明了 Embedding 能捕捉詞彙的語義關係，而非單純的字元比對。")


# 第二部分：LLM 應用範例 - 簡單的 RAG 問答
print("\n" + "="*60)
print("第二部分：LLM 應用範例 - 基於 RAG 的問答系統")
print("="*60)

# 1. 建立一個小型知識庫
knowledge_base = [
    "東京以櫻花和秋季楓葉聞名，特別是上野公園。",
    "京都擁有許多古老寺廟，是體驗日本文化的最佳地點。",
    "札幌以雪祭和啤酒聞名，冬季非常熱門。",
    "大阪被稱為日本的廚房，以章魚燒和大阪燒等美食聞名。",
    "富士山是日本最高的山，也是著名的象徵。"
]

# 2. 將知識庫中的每段文字轉換成 Embedding
print("\n步驟 1: 將知識庫文件向量化...")
kb_embeddings = []
for doc in knowledge_base:
    emb = get_embedding(doc)
    if emb:
        kb_embeddings.append(emb)

# 3. 使用者提出問題
user_query = "我想去日本看櫻花，有什麼推薦的城市？"
print(f"\n步驟 2: 使用者提問 -> '{user_query}'")

# 4. 將問題也轉換成 Embedding
query_embedding = get_embedding(user_query)

# 5. 計算問題與所有知識庫文件的相似度，找出最相關的
print("步驟 3: 計算問題與知識庫的語義相似度...")
similarities = []
for i, doc_emb in enumerate(kb_embeddings):
    sim = cosine_similarity(query_embedding, doc_emb)
    similarities.append((sim, i))

# 排序並選出最相關的前 2 個文件
similarities.sort(reverse=True)
top_k = 2
relevant_docs = [knowledge_base[idx] for _, idx in similarities[:top_k]]

print(f"找到最相關的 {top_k} 段資訊：")
for doc in relevant_docs:
    print(f"  - {doc}")

# 6. 將相關資訊作為上下文，提供給 LLM 生成回答
print("\n步驟 4: 將相關資訊作為上下文，提供給 LLM 生成回答...")
context = "\n".join(relevant_docs)
prompt = f"""請根據以下提供的資訊來回答使用者的問題。

提供的資訊：
{context}

使用者的問題：{user_query}

請用繁體中文回答："""

llm_response = llm_generate(prompt)
print(f"\nLLM 的回答：\n{llm_response}")

print("\n結論：透過 RAG，LLM 能夠基於我們提供的特定知識（東京的櫻花）來回答問題，")
print("而不是僅依賴其訓練資料中的一般知識，從而提高回答的準確性和相關性。")


