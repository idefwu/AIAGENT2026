import sys
from mcp.server.fastmcp import FastMCP
import chromadb
from sentence_transformers import SentenceTransformer

# 初始化 MCP 服務
mcp = FastMCP("Local-RAG-Knowledge-Base")

DB_PATH = "./my_vector_db"
COLLECTION_NAME = "my_rag_collection"

# 建立工具讓 Agent (例如 Claude) 能夠主動調用
@mcp.tool()
def query_knowledge_base(query: str, num_results: int = 2) -> str:
    """
    當使用者詢問關於本地知識庫、過去上傳的文字檔或特定商務法規內容時，
    調用此工具來檢索微軟 e5 多語言向量資料庫。
    
    :param query: 使用者的查詢提問句。
    :param num_results: 要撈出的相關知識塊數量。
    """
    try:
        # 連接與讀取 Streamlit 同步疊加的資料夾
        chroma_client = chromadb.PersistentClient(path=DB_PATH)
        collection = chroma_client.get_collection(name=COLLECTION_NAME)
        embed_model = SentenceTransformer("intfloat/multilingual-e5-base")
        
        # 執行向量轉換與檢索
        query_vector = embed_model.encode(f"query: {query}").tolist()
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=num_results
        )
        
        if not results['documents'] or len(results['documents'][0]) == 0:
            return "在向量資料庫中找不到任何相關參考資料。"
            
        # 格式化輸出回報給 Agent
        response_text = "📍 幫你從向量資料庫檢索到以下關聯內容：\n\n"
        for idx, doc in enumerate(results['documents'][0], 1):
            source = results['metadatas'][0][idx-1].get('source', '未知來源') if results['metadatas'] else '未知來源'
            response_text += f"【來源檔案: {source}】\n{doc}\n"
            response_text += "-" * 30 + "\n"
            
        return response_text
        
    except Exception as e:
        return f"檢索過程中發生錯誤: {str(e)}。請確認 Streamlit 介面是否已成功建立資料庫。"

if __name__ == "__main__":
    # MCP 伺服器預設透過標準輸入輸出 (stdio) 與大模型客戶端通訊
    mcp.run(transport='stdio')