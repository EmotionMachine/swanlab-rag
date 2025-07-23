# Swanlab文档助手技术方案

## 摘要：

为了让开发者能够更快速、更精准地从 SwanLab 官方文档中获取信息，我们开发了一款 AI 文档助手。它能理解自然语言提问，并结合最新的文档内容，给出准确的回答和参考来源，极大地提升了文档查阅效率。只需提问，立刻获取官方文档答案！本文详解SwanLab文档助手的技术实现，从数据准备到智能检索的全流程。

![image-20250724114933755](C:\Users\lichen\AppData\Roaming\Typora\typora-user-images\image-20250724114933755.png)

## 数据准备：AI 的知识源泉

### 1.文档检索：

 AI助手的知识基础来源于最新、最全的官方文档。我们首先需要让 AI 拥有“阅读”所有 SwanLab 官方文档的能力。我们编写了一个网络爬虫脚本，通过调用 GitHub API，自动扫描 SwanLab 文档仓库，获取所有 Markdown 文件的元数据，如标题、下载链接和对应的官网页面地址保存到`JSON`文件中。示例如下所示：


![image-20250724121726401](C:\Users\lichen\AppData\Roaming\Typora\typora-user-images\image-20250724121726401.png)

```json
{
      "theme": "cli-swanlab-convert",
      "url": "https://raw.githubusercontent.com/SwanHubX/SwanLab-Docs/main/zh/api/cli-swanlab-convert.md",
      "html_url": "https://docs.swanlab.cn/api/cli-swanlab-convert.html",
      "title": "swanlab convert"
 }
```

实现检索核心代码：

```python
#scrape_swanlab_docs_Internet.py
def scan_directory(url, docs, depth=0):
    if not check_rate_limit(headers, session):
        logger.error(f"{'  ' * depth}Skipping directory {url} due to rate limit check failure")
        return

    try:
        response = session.get(url, headers=headers, timeout=60)
        logger.info(f"{'  ' * depth}Fetching GitHub API {url}: Status {response.status_code}")
        response.raise_for_status()
        contents = response.json()

        for item in contents:
            if item['type'] == 'file' and item['name'].endswith('.md'):
                theme = item['name'].replace('.md', '')
                md_url = item['download_url']
                # 生成HTML URL
                relative_path = md_url.split('/main/zh/')[-1]
                html_filename = filename_map.get(theme, theme)
                html_path = relative_path.replace(theme + '.md', html_filename + '.html')
                html_url = f"{base_html_url}/{html_path}"
                # 提取标题
                title = get_markdown_title(md_url, headers, session)

                docs.append({
                    "theme": theme,
                    "url": md_url,
                    "html_url": html_url,
                    "title": title
                })
                logger.info(
                    f"{'  ' * depth}Added file: {theme}, Markdown: {md_url}, HTML: {html_url}, Title: {title}")
            elif item['type'] == 'dir':
                logger.info(f"{'  ' * depth}Entering directory: {item['path']}")
                scan_directory(item['url'], docs, depth + 1)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in [429, 403]:
            reset_time = int(e.response.headers.get('x-ratelimit-reset', 0))
            wait_time = reset_time - int(time.time()) + 1 if reset_time > 0 else 60
            logger.warning(f"{'  ' * depth}Rate limit error for {url}. Waiting {wait_time} seconds.")
            time.sleep(wait_time)
            scan_directory(url, docs, depth)
        else:
            logger.error(f"{'  ' * depth}Error scanning {url}: {str(e)}")
    except Exception as e:
        logger.error(f"{'  ' * depth}Error scanning {url}: {str(e)}")

# 扫描GitHub目录
api_url = repo_url.replace(
    "https://github.com/", "https://api.github.com/repos/"
).replace("/tree/main/", "/contents/")
logger.info(f"Starting scan of {repo_url}")
scan_directory(api_url, docs)

# 保存到JSON文件
try:
    json_path = r"swanlab.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"documents": docs}, f, ensure_ascii=False, indent=2)
    logger.info(f"JSON file created: {json_path} with {len(docs)} documents")
except Exception as e:
    logger.error(f"Error writing to JSON file: {str(e)}")

return docs
```

### 2.文档解析与分块合并：将文档Chunks化

 在上一步我们得到了所有文档的“地址列表”（`JSON` 文件）。接下来，我们需要“按图索骥”，访问每一个链接，异步地抓取所有 Markdown 的原始内容，使用LLM对每个文档根据内容进行文档解析与分块处理，采取其重要部分用于构建知识库。配置文件和分块提示词如`config.py`和`prompt.py`所示。在处理时，我们用一个特殊的分隔符 `################` 将文档内容按照二级标题的内容隔开，形成一个完整的Swanlab文档知识库。

```yaml
#config.yaml`
llm:
  api_type: "openai"  # 或 "groq" 等
  model: "Qwen/Qwen2.5-32B-Instruct"  # 或 "GPT-4o"等
  api_key: ""    #填写api_key
  base_url: ""  # LLM服务URL
```

```python
#prompt.py
llm = LLM()
prompt = f"""
分析以下 Markdown 内容，把内容进行分块整理。
格式如下所示：
一级标题：(文档标题)
二级标题（文档二级标题）：内容
################
一级标题：(文档标题)
二级标题（文档二级标题）：内容
################
......
################
参考内容：{content}
"""
```

将分块后的内容合并到一起，这样每个知识块都包含了相对完整的主题与内容，以便于后续的精确检索。实现这个逻辑的代码非常简单：

```python
# create_vector.py
def split_text(text: str, separator: str = "################") -> list[str]:
    """
    分割文本：根据指定的分隔符分割文本。
    """
    chunks = text.split(separator)
    # 过滤掉可能存在的空字符串
    return [chunk.strip() for chunk in chunks if chunk.strip()]
```



### 3.文档编码：将文字转化为“AI坐标”

现在我们有了一堆文本块，但计算机不理解文字，只懂数字。我们需要一个“翻译官”，把每个文本块翻译成一个由数字组成的“向量”（Vector）。这个过程就是 **Embedding**。我们调用了 SiliconFlow 平台提供的 `Qwen-Embedding` 模型来完成这个任务。对于这样的每一个文本块，我们都获得了一个Embedding后的向量。

```python
# create_vector.py
def get_embeddings_from_api(texts: list[str], batch_size: int = 16) -> list[list[float]]:
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
        # ... 发起请求并获取返回的向量 ...
        response_data = response.json()
        batch_embeddings = [item['embedding'] for item in response_data['data']]
        all_embeddings.extend(batch_embeddings)

    return all_embeddings
```

拿到所有向量后，我们使用 Facebook 开源的 `FAISS` 库来构建一个向量数据库。可以把它想象成一个专门为向量设计的高效“图书馆”，能极快地找到与给定向量最相似的几个向量，即获取相关性最高的几个文本块。

至此，我们的“Swanlab官方文档知识库”已经完全准备就绪了！我们就可以进行文档检索了!

## 文档检索：结合官方文档，让 AI “开卷考试”回答问题。

**目标：** 生动地解释 RAG 的核心检索与生成流程，让读者明白 AI 是如何利用前面的数据来回答问题的。

数据准备是离线完成的，而问答检索则是用户与 AI 实时交互的过程。这个过程就像让 AI 进行一场“开卷考试”，我们先把相关的参考资料（检索到的知识块）找出来，再让它根据这些官方资料来回答与解决用户问题。

### 1.检索：精准定位，解决问题

当用户提出一个问题时，我们首先用和之前完全相同的 Embedding 模型，将用户的**问题也转换成一个向量**。

![image-20250724145848506](C:\Users\lichen\AppData\Roaming\Typora\typora-user-images\image-20250724145848506.png)

然后，我们拿着这个“问题向量”，去 FAISS 向量数据库里进行搜索，命令它：“找出与我这个向量在空间距离上最接近文本块向量！"

```python
# chat_logic_loacl.py
# 1. 将用户问题转换为向量
query_embedding = self._get_query_embedding(question)
query_vector = np.array([query_embedding]).astype('float32')

# 2. 在FAISS中执行搜索，k=3表示寻找最相似的3个,可以动态调整
distances, indices = self.index.search(query_vector, k=3)

# 3. 根据返回的索引号，找到原始的文本块
retrieved_chunks = [self.index_to_chunk[str(i)] for i in indices[0]]
```

被检索出来的文本块，就是我们为 AI 准备的“小抄”，它们是与问题最相关的内容。

### 2.构建Prompt：精心设计“考题”

如果直接把“小抄”和问题扔给LLM的效果通常不好。我们需要精心设计一个“提示词”（Prompt），相当于给 AI 设定好角色和答题格式。让AI的回答更加人性化，条例清晰。

![image-20250724154459805](C:\Users\lichen\AppData\Roaming\Typora\typora-user-images\image-20250724154459805.png)

我们的 Prompt 模板大概是这样的：

```python
# chat_logic_loacl.py

# ... context = 拼接检索到的N个chunks ...
# ... history_prompt = 拼接历史对话 ...

prompt = f"""
# 角色
你是一个 SwanLab 开源项目的文档问答助手，需要基于上下文和历史对话进行回答。叙述风格具有一定的幽默成分。
例如：我是 SwanLab 文档问答小助手，一只聪明但不高冷的 AI 天鹅（不会嘎嘎叫，但会嘎嘎地帮你找文档）。我专注于回答 SwanLab 开源项目的各种文档问题，无论你是刚起飞的初学者，还是已经在模型训练池里畅游的大佬，只要你提问，我就能基于上下文和历史对话，精准定位知识点，快速响应需求。

# 历史对话记录
{history_prompt}

# 本次检索到的背景知识
[背景知识]
{context}

# 本次提问
[问题]
{question}
---
你的回答:
"""
```

这个精心构造的 Prompt，将所有必要信息都提供给了大模型，引导它做出最准确与最全面的回答。

### 3.生成并返回：给出答案和出处

最后一步，我们将这个完整的 Prompt 发送给一个强大的大语言模型（本项目使用 `Qwen/Qwen3-30B-A3B`），它会综合所有信息，生成一段流畅、准确的回答。

Qwen3（通义千问3）是阿里巴巴推出的新一代大语言模型，其核心技术特点包括多模态与超长上下文处理能力（支持图像、音频输入及128K上下文窗口）、高效的混合专家架构（MoE）优化（通过稀疏化设计降低70%训练成本并提升50%推理速度），以及强化推理与泛化能力（在MMLU、GPQA等评测中推理分数提升15%，代码生成HumanEval得分达85.3%）。该模型通过架构创新与垂直优化，在性能、效率及多任务适应性上实现突破，成为国产大模型的标杆之一。其中Qwen3系列模型的Agent能力得到了全面的加强，同时也加强了对 MCP 的支持。

![image-20250724151955944](C:\Users\lichen\AppData\Roaming\Typora\typora-user-images\image-20250724151955944.png)

更棒的是，我们还增加了一个小细节：从被检索到的知识块中，我们提取出它们的“一级标题”，并利用我们最早爬取到的 `html_url`，为用户生成一个可点击的“参考资料”列表，让答案更有权威性。为用户提供更多的参考与指南。

## 

