import os
import json
import sqlite3
from datetime import datetime
import requests
import numpy as np
import faiss
from collections import Counter
import re
from feishu_sync import sync_data_to_feishu
import time
#RAG查询时间，响应时间（分＋总），回复时间


class Chatbot:
    def __init__(self,
                 index_path="faiss_index_scratch_1",
                 url_map_path="swanlab_docs_Internet8-2.json",
                 db_path="user_questions1.db"):
        print("正在初始化 Chatbot...")
        self.FAISS_INDEX_PATH = index_path
        self.URL_MAP_PATH = url_map_path
        self.LLM_API_KEY = "bcbe32ab-3117-4225-a751-c6aa24309de0"
        self.LLM_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
        self.LLM_MODEL = "doubao-1-5-pro-32k-250115"
        self.EMB_API_KEY = "sk-ebaafxbagclzofzsruircunkmyizeytezzkkgdilzydpdxae"
        self.EMB_BASE_URL = "http://api.siliconflow.cn/v1"
        self.EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
        self.VECTOR_DIMENSION = 1024

        self.db = self._init_database(db_path)
        self.url_map = self._load_url_map(self.URL_MAP_PATH)
        self.index, self.index_to_chunk = self._load_vector_store(self.FAISS_INDEX_PATH)
        self.VERSION = "V1.0"
        print("Chatbot 初始化完成！")

    def _init_database(self, db_path):
        print(f"Initializing database at: {db_path}")
        conn = sqlite3.connect(db_path, check_same_thread=False)
        cursor = conn.cursor()
        try:
            # 创建用户表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    enter_time TEXT NOT NULL,
                    exit_time TEXT,
                    question_count INTEGER DEFAULT 0
                )
            """)

            # 创建问题表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    feedback TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # 检查表是否创建成功
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"Tables in database: {[table[0] for table in tables]}")

            conn.commit()
            print("Database initialized successfully")
            return conn
        except sqlite3.Error as e:
            print(f"Database initialization error: {e}")
            return None

    def _load_url_map(self, json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {item['title']: item['html_url'] for item in data if 'title' in item and 'html_url' in item}
        except Exception as e:
            print(f"Error loading URL map: {e}")
            return {}

    def _load_vector_store(self, index_path):
        try:
            index_file = os.path.join(index_path, "index.faiss")
            map_file = os.path.join(index_path, "index_to_chunk.json")
            index = faiss.read_index(index_file)
            with open(map_file, 'r', encoding='utf-8') as f:
                index_to_chunk = json.load(f)
            print(f"向量数据库加载成功，包含 {index.ntotal} 个向量。")
            return index, index_to_chunk
        except Exception as e:
            print(f"错误：无法加载向量数据库。错误: {e}")
            return None, None

    def _get_query_embedding(self, text):
        headers = {"Authorization": f"Bearer {self.EMB_API_KEY}", "Content-Type": "application/json"}
        url = f"{self.EMB_BASE_URL.rstrip('/')}/embeddings"
        payload = {"model": self.EMBEDDING_MODEL, "input": [text]}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()['data'][0]['embedding']



    def get_user_enter_time(self, user_id):
        """根据 user_id 从数据库获取用户的进入时间"""
        if not self.db:
            return None
        try:
            cursor = self.db.cursor()
            cursor.execute("SELECT enter_time FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            print(f"查询用户进入时间失败: {e}")
            return None

    def create_user(self, user_id):
        """创建新用户记录"""
        print(f"Attempting to create user with ID: {user_id}")
        if not self.db:
            print("Database connection is None")
            return None
        try:
            cursor = self.db.cursor()
            enter_time = datetime.now().isoformat()
            print(f"Inserting user: {user_id}, enter_time: {enter_time}")

            # 检查用户是否已存在
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            existing_user = cursor.fetchone()
            if existing_user:
                print(f"User {user_id} already exists")
                return user_id

            # 插入新用户
            cursor.execute(
                "INSERT INTO users (user_id, enter_time) VALUES (?, ?)",
                (user_id, enter_time)
            )
            self.db.commit()

            # 验证用户是否成功创建
            cursor.execute("SELECT user_id, enter_time FROM users WHERE user_id = ?", (user_id,))
            new_user = cursor.fetchone()
            if new_user:
                print(f"User {user_id} created successfully with enter_time: {new_user[1]}")
                return user_id
            else:
                print(f"Failed to create user {user_id}")
                return None
        except sqlite3.Error as e:
            print(f"Database error creating user: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error creating user: {e}")
            return None

    def update_user_exit(self, user_id):
        """更新用户退出时间"""
        print(f"Attempting to update exit time for user: {user_id}")
        if not self.db:
            print("Database connection is None")
            return
        try:
            cursor = self.db.cursor()
            exit_time = datetime.now().isoformat()
            print(f"Updating user exit time: {user_id}, exit_time: {exit_time}")
            cursor.execute(
                "UPDATE users SET exit_time = ? WHERE user_id = ?",
                (exit_time, user_id)
            )
            self.db.commit()
            print(f"User {user_id} exit time updated successfully")
        except sqlite3.Error as e:
            print(f"Database error updating user exit: {e}")
        except Exception as e:
            print(f"Unexpected error updating user exit: {e}")

    def increment_question_count(self, user_id):
        """增加用户问题计数"""
        if not self.db:
            return
        try:
            cursor = self.db.cursor()
            cursor.execute(
                "UPDATE users SET question_count = question_count + 1 WHERE user_id = ?",
                (user_id,)
            )
            self.db.commit()
        except sqlite3.Error as e:
            print(f"Database error incrementing question count: {e}")

    def save_question(self, user_id, question, answer):
        """保存问题记录"""
        if not self.db:
            return None
        try:
            cursor = self.db.cursor()
            cursor.execute(
                "INSERT INTO questions (user_id, question, answer) VALUES (?, ?, ?)",
                (user_id, question, answer)
            )
            self.db.commit()
            question_id = cursor.lastrowid
            self.increment_question_count(user_id)
            return question_id
        except sqlite3.Error as e:
            print(f"Database error saving question: {e}")
            return None

    def add_feedback(self, question_id, feedback):
        """保存用户反馈，并只触发飞书同步"""
        if not self.db or not question_id:
            return "数据库未连接或问题ID为空。"
        if feedback not in ["correct", "incorrect"]:
            return "无效的反馈。"
        try:
            # 更新本地数据库
            cursor = self.db.cursor()
            cursor.execute(
                "UPDATE questions SET feedback = ? WHERE id = ?",
                (feedback, question_id)
            )
            self.db.commit()
            print(f"本地数据库反馈已保存: question_id={question_id}, feedback={feedback}")

            # --- 3. 修改点：只调用同步函数来更新反馈 ---
            feishu_data = {
                "question_id": question_id,
                "feedback": feedback
            }
            sync_data_to_feishu(feishu_data)
            # ------------------------------------------

            return f"感谢您的反馈！"
        except sqlite3.Error as e:
            print(f"Database error saving feedback: {e}")
            return "更新反馈失败。"

    @staticmethod
    def _extract_h1_title(text: str) -> str:
        prefix = "一级标题："
        for line in text.split('\n'):
            if line.startswith(prefix):
                return line[len(prefix):].strip()
        return ""

    def _keyword_search(self, query: str, k: int = 10):
        keywords = [word for word in re.split(r'\W+', query.lower()) if word]
        if not keywords:
            return []

        all_chunks = list(self.index_to_chunk.values())
        chunk_scores = {}

        for chunk in all_chunks:
            score = 0
            chunk_lower = chunk.lower()
            for keyword in keywords:
                score += chunk_lower.count(keyword)

            if score > 0:
                chunk_scores[chunk] = score

        sorted_chunks = sorted(chunk_scores.items(), key=lambda item: item[1], reverse=True)
        return [chunk for chunk, score in sorted_chunks[:k]]

    def stream_chat(self, question, history, user_id):
        # --- 1. 记录流程开始时间 ---
        start_time = time.time()
        # ------------------------
        if not self.index or not self.index_to_chunk:
            yield "错误：向量数据库未加载。", None
            return

        # 检索阶段
        query_embedding = self._get_query_embedding(question)
        query_vector = np.array([query_embedding]).astype('float32')
        distances, indices = self.index.search(query_vector, k=10)
        vector_retrieved_chunks = [self.index_to_chunk[str(i)] for i in indices[0]]

        keyword_retrieved_chunks = self._keyword_search(question, k=10)

        # 合并与去重
        combined_chunks = {}
        all_retrieved = vector_retrieved_chunks + keyword_retrieved_chunks

        for chunk in all_retrieved:
            processed_chunk = chunk
            if isinstance(chunk, list):
                processed_chunk = "\n".join(chunk)

            if isinstance(processed_chunk, str) and processed_chunk:
                combined_chunks[processed_chunk] = None

        retrieved_chunks = list(combined_chunks.keys())

        # 标题分析
        all_h1_titles = [self._extract_h1_title(chunk) for chunk in retrieved_chunks if self._extract_h1_title(chunk)]
        title_counts = Counter(all_h1_titles)
        print(f"title_counts: {title_counts}")
        top_titles = [title for title, count in title_counts.items() if count >= 2]
        print(f"top_titles: {top_titles}")

        # --- 2. 记录检索完成时间 ---
        rag_end_time = time.time()
        rag_duration = rag_end_time - start_time
        print(f"检索阶段耗时: {rag_duration:.2f} 秒")
        # ------------------------

        # 构建Prompt
        context = "\n\n---\n\n".join(retrieved_chunks)
        history_prompt = "👋 你好！我是SwanLab文档的智能问答助手。🤖请问有什么可以帮助您的吗？😊".join([f"历史提问: {u}\n历史回答: {a}\n\n" for u, a in history])
        print(f"history_prompt:{history_prompt}")

        prompt = f"""
                # 角色
                你是一个 SwanLab 开源项目的文档问答助手，你是一个 SwanLab 开源项目的文档问答助手，Swanlab是由情感机器（北京）科技有限公司推出的产品。
                #指令
                1，根据提供的 [背景知识] 回答 [问题]。如果未找到任何相关的，则提醒用户未找到参考资料，根据你现有的知识给予意见。
                2.回答时，叙述风格可以使用一些图标，使其更人性化。
                4.如果遇到图片的相对地址，回答的时候不参考图片。
                5.如果遇到一些网页地址存在不够完整，请在地址前面添加"https://docs.swanlab.cn/",并且把".md"替换为".html"。
                6.同时也结合用户历史提到的问题是否与当前问题是否存在相关性，结合起来回答。
                ---
                [历史问题]
                {history_prompt}
                ---
                [背景知识]
                {context}
                ---
                # 本次提问
                [问题]
                {question}
                ---
                你的回答:
                """

        current_model_prompt = """
                # 角色
                你是一个 SwanLab 开源项目的文档问答助手，你是一个 SwanLab 开源项目的文档问答助手，Swanlab是由情感机器（北京）科技有限公司推出的产品。
                #指令
                1，根据提供的 [背景知识] 回答 [问题]。如果未找到任何相关的，则提醒用户未找到参考资料，根据你现有的知识给予意见。
                2.回答时，叙述风格可以使用一些图标，使其更人性化。
                3.回答完成后，可以反问用户一些相关的问题。
                4.如果遇到图片的相对地址，回答的时候不参考图片。
                5.如果遇到一些网页地址存在不够完整，请在地址前面添加"https://docs.swanlab.cn/",并且把".md"替换为".html"。
                6.同时也结合用户历史提到的问题是否与当前问题是否存在相关性，结合起来回答。
                ---
                [历史问题]
                {}
                ---
                [背景知识]
                {}
                ---
                # 本次提问
                [问题]
                {}
                ---
                你的回答:
                """

        print(f'current_model_prompt:{current_model_prompt}')
        # 发送请求
        headers = {"Authorization": f"Bearer {self.LLM_API_KEY}", "Content-Type": "application/json"}
        url = f"{self.LLM_BASE_URL.rstrip('/')}/chat/completions"
        payload = {"model": self.LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "stream": True}

        # 流式处理响应
        full_answer = ""
        first_token_time = None  # 初始化首个 token 时间
        first_token_recorded = False  # 添加一个标志位
        try:
            with requests.post(url, headers=headers, json=payload, stream=True, timeout=100) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            json_str = decoded_line[len("data: "):]
                            if json_str.strip() == "[DONE]":
                                break
                            try:
                                data = json.loads(json_str)
                                if 'choices' in data and data['choices'][0].get('delta', {}).get('content'):

                                    # --- 3. 记录首个 Token 时间 ---
                                    if not first_token_recorded:
                                        first_token_time = time.time()
                                        first_token_duration = first_token_time - rag_end_time
                                        print(f"LLM 首个 Token 响应耗时: {first_token_duration:.2f} 秒")
                                        first_token_recorded = True  # 确保只记录一次
                                    # ----------------------------

                                    token = data['choices'][0]['delta']['content']
                                    full_answer += token
                                    yield full_answer, None
                            except json.JSONDecodeError:
                                continue

            # --- 4. 记录回答完成时间 ---
            llm_end_time = time.time()
            # 计算从收到首个 token 到回答结束的耗时
            llm_response_duration = llm_end_time - (first_token_time if first_token_time else rag_end_time)
            # 计算整个流程的总耗时
            total_duration = llm_end_time - start_time
            print(f"LLM 输出完成耗时: {llm_response_duration:.2f} 秒")
            print(f"总流程耗时: {total_duration:.2f} 秒")
            # --------------------------

            # --- 这是数据记录到飞书修改点 ---
            # 1. 保存到本地数据库并获取 question_id
            question_id = self.save_question(user_id, question, full_answer)

            # 2. 准备同步到飞书的完整数据
            enter_time_str = self.get_user_enter_time(user_id)
            enter_time_timestamp = int(
                datetime.fromisoformat(enter_time_str).timestamp() * 1000) if enter_time_str else None

            feishu_data = {
                "question_id": question_id,
                "user_id": user_id,
                "enter_time": enter_time_timestamp,  # 飞书日期需要毫秒级时间戳
                "question": question,
                "retrieved_chunks_content": context,
                "retrieved_title_statistics": json.dumps(title_counts, ensure_ascii=False, indent=2),
                "answer": full_answer,

                ##新增列表
                "history_prompt": history_prompt,
                "model_prompt": current_model_prompt,
                "embedding_model": self.EMBEDDING_MODEL,  #增加
                "llm_model": self.LLM_MODEL,
                "version": self.VERSION,
                "rag_duration": f"{rag_duration:.2f}",
                "first_token_duration": f"{first_token_duration:.2f}" if first_token_recorded else "N/A",
                "llm_response_duration": f"{llm_response_duration:.2f}",
                "total_duration": f"{total_duration:.2f}"
            }

            # 3. 调用同步函数
            sync_data_to_feishu(feishu_data)
            # --- 修改结束 ---

            # 4. 格式化并添加参考资料
            source_documents = []
            for title in top_titles:
                html_url = self.url_map.get(title)
                print(f"title:{title}")
                print(f"url:{html_url}")
                source_documents.append({"title": title, "html_url": html_url})

            if source_documents:
                sources_md = "\n\n---\n\n📚 **参考资料：**\n"
                for doc in source_documents:
                    if doc.get('html_url'):
                        sources_md += f"- [{doc['title']}]({doc['html_url']})\n"
                full_answer += sources_md
                yield full_answer, question_id

        except requests.exceptions.RequestException as e:
            yield f"API 请求失败: {e}", None