# Swanlab-RAG文档助手构建教程

SwanLab AI 文档助手`🤖`是一个基于 RAG (Retrieval-Augmented Generation) 技术的Agent问答系统，专门针对 SwanLab 官方文档构建。它能够理解您的问题，从文档中检索相关信息，并提供准确的回答。

该项目使用Gradio构建  Web 用户界面`🌐`，用户可以直接在聊天框输入问题，模型会基于 SwanLab 官方文档内容回答问题并且提供回答所依据的文档链接。

<div align="center">
  <figure>
  <img src="./assets/rag-login.png" alt="rag-demo"  width="800" />
  <figcaption>Swanlab官方文档入口</figcaption>
  </figure>
</div>
Swnlab文档助手在线使用链接：[https://chat.swanlab.cn/](https://chat.swanlab.cn/)

------





## 主要功能

- **文档获取**：`Agent`首先会获取目标地址的所有`Markdown`文件，并整理成`Json`格式（包含`title, base_url, html_url` 等字段）。

- **文档分块**：依次读取每个`Markdown`文档，按二级标题整理为`Chunk`。

- **文档检索**：从`Swanlab`文档中检索最相关的信息片段，增强回答的准确性。

- **智能问答**：使用`Gradio`构建前端交互页面，基于`Swanlab`官方文档内容，提供准确的问答服务。

  ------

  

## 快速开始

### ⚙️环境配置

- #### 基础环境

  推荐：python>=3.10	

  ```bash
  # 使用conda创建环境
  
  conda create -n RAG python=3.10
  
  # 安装相关依赖
  
  pip install aiohttp requests faiss-cpu numpy sqlite3 gradio flask 
  ```

- #### 可选依赖

	如果使用本地 Embedding 模型而非 API，需要安装`sentence-transformers`

	```bash
	pip install sentence-transformers
	```

- #### **API密钥配置**🔑

​	代码中需要填写以下密钥（在 `chat_logic_deploy.py` 和 `create_verctor.py` 中）：

```python
API_KEY = "填写API_KEY"              # 例如 OpenAI 或本地模型的 API 密钥
BASE_URL = "填写API的base_url"       # 如 "https://api.openai.com/v1"
EMBEDDING_MODEL = "填写Embedding模型" # 如 "text-embedding-3-small"
LLM_MODEL = "填写LLM模型"            # 如 "gpt-3.5-turbo"
```


### 📄文件结构

	确保项目目录包含以下文件：
	    .
	    ├──Search/
	    │ 	├──documents_analyzer_url.py	# 文档解析与分块
	    │   ├──scrape_docs_Internet.py		# 获取文档
	    │   ├── content.py                  # 内容提取工具
	    ├── faiss_index_scratch_1/       	# 向量数据库目录（自动生成）
	    │   ├── index.faiss              	# Faiss 索引文件
	    │   └── index_to_chunk.json      	# 向量-文本映射
	    ├── create_verctor.py            	# 向量数据库生成
	    ├── chat_logic_deploy.py         	# 聊天逻辑与数据库
	    ├── app_deploy.py                	# Gradio 交互界面
	    ├── swanlab_docs_Internet8-2.json 	# 文档元数据（URL/标题映射）
	    └── document_blocks.txt          	# 分块后的文档内容（可选）

------

## 部署与运行**🚀** 

- **克隆或下载项目**: 将本项目所有文件放置在您电脑上的一个文件夹中。或者参考本项目自己构建。

- **获取知识库文档**（首次运行）：依次顺序执行🔄，修改保存文件到指定目录。或者运行如下`bash`指令，保存默认地址。

```bash
# 1. 先爬取文档并生成JSON（如果需要更新文档）
python scrape_swanlab_docs_Internet.py && \

# 2. 解析文档并分块存储
python documents_analyzer_url.py && \

# 3. 拼接文档块
python content.py && \
```

- 生成向量数据库（首次运行）：

    ```bash
    python create_verctor.py
    ```

- 启动Web服务：

    ```bash
    python app_deploy.py
    ```

	- 默认访问地址：`http://localhost:7860`

    - 如需 HTTPS，需配置 SSL 证书路径（修改 `app_deploy.py` 中的 `ssl_keyfile` 和 `ssl_certfile`）。

------

## 注意事项⚠️ 

-  **GitHub Token🔑**（可选）
   - 如果从 GitHub 爬取文档（`scrape_swanlab_docs_Internet.py`），需在代码中替换 `GITHUB_TOKEN`。
-  **Faiss 版本兼容性🐍**
   - 确保 `faiss-cpu` 或 `faiss-gpu` 版本与 Python 环境匹配。
-  **资源占用**📊
   - 向量检索可能消耗内存，建议至少 4GB 可用内存。
-  **网络请求**🌐
   - 如果使用外部 API（如 OpenAI），需确保网络能访问 `BASE_URL`。
