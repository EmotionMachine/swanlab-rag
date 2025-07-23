import json
import aiohttp
import asyncio
import re
import os
import logging
from pathlib import Path
import time

# 配置日志
log_path = os.path.join(os.path.dirname(__file__), "document_processor.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 配置GitHub Token（替换为你的Token）
GITHUB_TOKEN = "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"  # 替换为 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'


async def check_rate_limit(session):
    """检查GitHub API速率限制"""
    try:
        async with session.get("https://api.github.com/rate_limit") as response:
            if response.status == 200:
                rate_data = await response.json()
                remaining = rate_data["rate"]["remaining"]
                reset_time = rate_data["rate"]["reset"]
                logging.info(f"Rate limit: {remaining} requests remaining, resets at {time.ctime(reset_time)}")
                if remaining == 0:
                    wait_time = reset_time - int(time.time()) + 1
                    if wait_time > 0:
                        logging.warning(f"Rate limit exceeded. Waiting {wait_time} seconds.")
                        await asyncio.sleep(wait_time)
                        return False
                return True
            else:
                logging.error(f"Failed to check rate limit: Status {response.status}")
                return True
    except Exception as e:
        logging.error(f"Error checking rate limit: {str(e)}")
        return True


async def fetch_url_content(session, url):
    """从URL获取内容"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124',
        'Accept': 'application/vnd.github.v3+json'
    }
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

    try:
        async with session.get(url, timeout=60) as response:
            if response.status == 200:
                content = await response.text()
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else "无标题"
                logging.info(f"Fetched content from URL: {url}, title: {title}")
                return {"content": content, "title": title}
            else:
                logging.error(f"Failed to fetch {url}: Status {response.status}")
                return {"content": "", "title": "无标题"}
    except asyncio.TimeoutError:
        logging.error(f"Timeout fetching URL: {url}")
        return {"content": "", "title": "无标题"}
    except Exception as e:
        logging.error(f"Error fetching URL {url}: {str(e)}")
        return {"content": "", "title": "无标题"}


async def fetch_content(source: dict) -> dict:
    """从URL或本地文件获取内容"""
    url = source.get('url', '')
    path = source.get('path', '')

    # 创建HTTP会话
    async with aiohttp.ClientSession() as session:
        # 检查GitHub API速率限制
        if url and ('github.com' in url or 'api.github.com' in url):
            await check_rate_limit(session)

        # 优先尝试URL
        if url:
            # 处理GitHub原始内容URL
            if url.startswith('https://github.com/') and '/blob/' in url:
                # 转换为原始内容URL
                raw_url = url.replace('github.com', 'raw.githubusercontent.com').replace('/blob/', '/')
                return await fetch_url_content(session, raw_url)
            # 处理GitHub API URL
            elif url.startswith('https://api.github.com/'):
                return await fetch_url_content(session, url)
            # 处理其他URL
            else:
                return await fetch_url_content(session, url)

        # 回退到本地文件
        elif path:
            try:
                abs_path = os.path.abspath(path)
                if not os.path.exists(abs_path):
                    raise FileNotFoundError(f"文件不存在: {abs_path}")
                with open(abs_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                title = title_match.group(1).strip() if title_match else "无标题"
                logging.info(f"Read content from local file: {abs_path}, title: {title}")
                return {"content": content, "title": title}
            except Exception as e:
                logging.error(f"Error reading file {path}: {str(e)}")
                return {"content": "", "title": "无标题"}
        else:
            logging.error("No valid URL or path provided")
            return {"content": "", "title": "无标题"}


def parse_markdown_blocks(content: str) -> list:
    """
    使用纯Python解析Markdown文档，按照一级标题和二级标题进行分块整理

    参数:
        content: Markdown文档内容

    返回:
        分块整理后的列表，每个元素是一个字典:
        {
            "h1": "一级标题",
            "h2": "二级标题",
            "content": "内容"
        }
    """
    if not content:
        return []

    # 按行分割内容
    lines = content.split('\n')

    # 初始化变量
    blocks = []
    main_title = None
    current_h2 = None
    current_content = []
    found_main_title = False

    # 遍历每一行
    for line in lines:
        # 寻找一级标题（必须顶格，且#后面有空格）
        if not found_main_title and line.startswith('# ') and line[0] == '#' and line[1] == ' ':
            main_title = line[2:].strip()
            found_main_title = True
            continue  # 跳过一级标题行，不加入内容

        # 如果已经找到一级标题，则开始处理内容
        if found_main_title:
            # 寻找二级标题（必须顶格，且##后面有空格）
            if line.startswith('## ') and line[0] == '#' and line[1] == '#' and line[2] == ' ':
                # 如果之前有内容，保存当前块
                if current_content or current_h2 is not None:
                    save_block(blocks, main_title, current_h2, current_content)

                # 设置新的二级标题
                current_h2 = line[3:].strip()
                current_content = []
                continue  # 跳过二级标题行，不加入内容

            # 添加内容行
            current_content.append(line)

    # 保存最后一个块
    if found_main_title and (current_content or current_h2 is not None):
        save_block(blocks, main_title, current_h2, current_content)

    return blocks


def save_block(blocks, h1, h2, content):
    """保存当前块到块列表"""
    # 清理内容：去除末尾空行
    while content and not content[-1].strip():
        content.pop()

    blocks.append({
        'h1': h1,
        'h2': h2,
        'content': '\n'.join(content).strip()
    })


def extract_filename(source: dict) -> str:
    """从URL或路径提取文件名"""
    url = source.get('url', '')
    path = source.get('path', '')
    try:
        if url:
            filename = url.split('/')[-1]
            return filename if filename.endswith('.md') else "unknown.md"
        elif path:
            filename = os.path.basename(path)
            return filename if filename.endswith('.md') else "unknown.md"
        else:
            return "unknown.md"
    except Exception as e:
        logging.error(f"Error extracting filename from {url or path}: {str(e)}")
        return "unknown.md"


async def process_document(source: dict) -> dict:
    """处理单个文档"""
    # 获取内容和标题
    result = await fetch_content(source)
    content = result["content"]
    title = result["title"]

    # 生成内容分块
    content_blocks = parse_markdown_blocks(content)

    # 提取文件名
    filename = extract_filename(source)

    # 返回结果字典
    return {
        "url": source.get("url", ""),
        "html_url": source.get("html_url", ""),
        "content_blocks": content_blocks,
        "filename": filename,
        "title": title
    }


def generate_txt_file(documents, output_path="document_blocks.txt"):
    """
    生成包含所有分块内容的txt文档，按照指定格式

    参数:
        documents: 处理后的文档列表
        output_path: 输出文件路径
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # 遍历所有文档的所有分块
            for doc in documents:
                for block in doc['content_blocks']:
                    # 写入一级标题
                    f.write(f"一级标题：{block['h1']}\n")

                    # 写入二级标题（如果没有则为"无"）
                    h2_text = block['h2'] if block['h2'] else "无"
                    f.write(f"二级标题：{h2_text}\n")

                    # 写入内容
                    f.write("内容：\n")
                    f.write(block['content'] + "\n")

                    # 写入块结束标记
                    f.write("################\n")

        logging.info(f"TXT文件已生成: {output_path}")
        return True
    except Exception as e:
        logging.error(f"生成TXT文件失败: {str(e)}")
        return False


async def main():
    """主函数，处理JSON文件中的文档列表"""
    # 读取 JSON 文件
    try:
        with open('swanlab_docs_Internet8-2.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        logging.error("Error: swanlab.json not found")
        return
    except json.JSONDecodeError:
        logging.error("Error: Invalid JSON format in swanlab.json")
        return

    updated_documents = []

    # 处理每个文档
    for doc in data['documents']:
        try:
            source = {"url": doc.get('url', ''), "html_url": doc.get('html_url', '')}
            if not source['url'] and not source['html_url']:
                raise ValueError("文档中未找到有效URL或路径")

            result = await process_document(source)
            updated_documents.append(result)
            logging.info(f"成功处理文档: {source['url'] or source['html_url']}")
        except Exception as e:
            logging.error(f"处理文档 {source.get('url', source.get('html_url', '未知'))} 出错: {str(e)}")
            updated_documents.append({
                "content_blocks": [],
                "filename": "unknown.md",
                "title": "无标题",
                "url": source.get('url', ''),
                "html_url": source.get('html_url', '')
            })

    # 更新 JSON 数据
    data['documents'] = updated_documents

    # 写回 JSON 文件
    try:
        with open('swanlab_docs_Internet-1.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info("JSON file updated successfully")
    except Exception as e:
        logging.error(f"Error writing to JSON file: {str(e)}")

    # 生成TXT文件
    generate_txt_file(updated_documents)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except asyncio.CancelledError:
        logging.error("主程序收到 CancelledError，可能是任务被取消或中断")
    except Exception as e:
        logging.error(f"主程序异常：{str(e)}")