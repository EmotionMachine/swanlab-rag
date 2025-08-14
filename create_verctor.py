import os
import json
import requests
import numpy as np
import faiss
import time

# --- 配置信息 ---
# 源文档路径
SOURCE_DOCUMENT_PATH = "Search/document_blocks.txt"
# 本地向量数据库的保存路径
FAISS_INDEX_PATH = "faiss_index_scratch_1"

# Embedding 模型配置
EMBEDDING_MODEL = "填写Embedding模型"##Qwen/Qwen3-Embedding-0.6B
API_KEY = "填写API_KEY"
BASE_URL = "填写API的base_url"
VECTOR_DIMENSION = 1024  # 向量维度


# --- 自定义函数 ---

def load_text(file_path: str) -> str:
    """
    加载数据：从文件中读取全部文本内容。
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def split_text(text: str, separator: str = "################") -> list[str]:
    """
    分割文本：根据指定的分隔符分割文本。
    """
    chunks = text.split(separator)
    # 过滤掉可能存在的空字符串
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def get_embeddings_from_api(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    """
    获取api：直接调用 API 获取 embedding 向量。
    处理了批量请求以提高效率并避免超出API单次请求的限制。
    """
    all_embeddings = []
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL.rstrip('/')}/embeddings"

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        payload = {
            "model": EMBEDDING_MODEL,
            "input": batch
        }

        print(f"  正在处理批次 {i // batch_size + 1} / {len(texts) // batch_size + 1}...")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()  # 如果请求失败 (非 2xx 状态码), 则抛出异常

            response_data = response.json()
            batch_embeddings = [item['embedding'] for item in response_data['data']]
            all_embeddings.extend(batch_embeddings)

        except requests.exceptions.RequestException as e:
            print(f"错误：API 请求失败: {e}")
            # 如果一个批次失败，可以选择停止或跳过
            # 这里我们选择停止，因为数据不完整可能导致后续问题
            raise

        # 速率限制，避免过于频繁地请求API
        time.sleep(0.1)

    return all_embeddings


def main():
    """
    主函数，用于创建和保存向量数据库，不使用 LangChain。
    """
    print("开始创建向量数据库 (从零开始)...")

    # 1. 加载文档
    print(f"正在从 '{SOURCE_DOCUMENT_PATH}' 加载文档...")
    full_text = load_text(SOURCE_DOCUMENT_PATH)
    print("文档加载完成。")

    # 2. 分割文档
    print("正在分割文档成 chunks...")
    chunks = split_text(full_text)
    print(f"文档分割完成，共得到 {len(chunks)} 个 chunks。")

    # 3. 获取所有 chunks 的 embedding 向量
    print("正在通过 API 获取所有 chunks 的 Embedding... (这可能需要一些时间)")
    embeddings = get_embeddings_from_api(chunks)
    print(f"Embedding 获取完成，共得到 {len(embeddings)} 个向量。")

    if len(embeddings) != len(chunks):
        print("错误：获取到的向量数量与 chunks 数量不匹配，程序终止。")
        return

    # 4. 创建并构建 FAISS 索引
    print("正在创建 FAISS 索引...")
    # 将 embedding 列表转换为 numpy 数组，FAISS 需要这种格式
    vectors_np = np.array(embeddings).astype('float32')

    # 创建一个基础的 L2 距离索引
    index = faiss.IndexFlatL2(VECTOR_DIMENSION)

    # 将向量添加到索引中
    index.add(vectors_np)
    print(f"FAISS 索引创建完成，索引中包含 {index.ntotal} 个向量。")

    # 5. 保存索引和内容映射到本地
    print(f"正在保存索引和内容到本地文件夹: '{FAISS_INDEX_PATH}'...")
    if not os.path.exists(FAISS_INDEX_PATH):
        os.makedirs(FAISS_INDEX_PATH)

    # 保存 FAISS 索引文件
    faiss.write_index(index, os.path.join(FAISS_INDEX_PATH, "index.faiss"))

    # 创建并保存从索引ID到原始文本块的映射
    # 这是至关重要的一步，因为 FAISS 只保存向量，不保存内容
    index_to_chunk = {i: chunk for i, chunk in enumerate(chunks)}
    with open(os.path.join(FAISS_INDEX_PATH, "index_to_chunk.json"), 'w', encoding='utf-8') as f:
        json.dump(index_to_chunk, f, ensure_ascii=False, indent=4)

    print("向量数据库已成功保存！")
    print(f"文件夹 '{FAISS_INDEX_PATH}' 中应包含 'index.faiss' 和 'index_to_chunk.json' 两个文件。")


if __name__ == "__main__":
    main()