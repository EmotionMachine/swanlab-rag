import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def check_rate_limit(headers, session):
    """
    检查GitHub API限额状态，若超限则等待重置。
    """
    try:
        response = session.get("https://api.github.com/rate_limit", headers=headers, timeout=60)
        response.raise_for_status()
        rate_limit_data = response.json()["rate"]
        remaining = rate_limit_data["remaining"]
        reset_time = rate_limit_data["reset"]
        logger.info(f"Rate limit: {remaining} requests remaining, resets at {time.ctime(reset_time)}")

        if remaining == 0:
            wait_time = reset_time - int(time.time()) + 1
            if wait_time > 0:
                logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds until reset.")
                time.sleep(wait_time)
                return check_rate_limit(headers, session)
        return True
    except Exception as e:
        logger.error(f"Error checking rate limit: {str(e)}")
        return False


def get_markdown_title(md_url, headers, session):
    """
    下载Markdown文件到内存并提取一级标题（# Title），运行结束释放。
    """
    try:
        response = session.get(md_url, headers=headers, timeout=60)
        response.raise_for_status()
        content = response.text
        # 匹配一级标题（# Title）
        match = re.search(r'^# (.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        logger.warning(f"No level-1 heading found in {md_url}, using empty title")
        return ""
    except Exception as e:
        logger.error(f"Error fetching title from {md_url}: {str(e)}")
        return ""


def scrape_web_docs(repo_url, base_html_url="https://docs.swanlab.cn", token=None):
    """
    递归扫描GitHub仓库zh目录，收集所有 .md 文件的URL、HTML URL和标题，
    生成 swanlab_docs_Internet.json，包含 theme、url、html_url 和 title。
    Markdown内容仅在内存中处理，运行结束释放。

    Args:
        repo_url (str): GitHub仓库目录URL（例如 'https://github.com/SwanHubX/SwanLab-Docs/tree/main/zh'）
        base_html_url (str): SwanLab文档网站根URL（例如 'https://docs.swanlab.cn'）
        token (str, optional): GitHub Personal Access Token，提高API限额

    Returns:
        list: 包含文档信息的列表，每个文档包含 theme、url、html_url 和 title
    """
    docs = []

    # 配置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/vnd.github.v3+json'
    }
    if token:
        headers['Authorization'] = f'token {token}'

    # 配置重试机制
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    # 手动文件名映射
    filename_map = {

    }

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
                    # 生成HTML URL，去掉 zh/
                    relative_path = md_url.split('/main/zh/')[-1]
                    html_filename = filename_map.get(theme, theme)
                    html_path = relative_path.replace(theme + '.md', html_filename + '.html')
                    html_url = f"{base_html_url}/{html_path}"
                    # 提取标题（内存中处理）
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
        if len(docs) < 142:
            logger.warning(f"Expected Markdown files, but found {len(docs)}")
    except Exception as e:
        logger.error(f"Error writing to JSON file: {str(e)}")

    return docs


if __name__ == "__main__":
    repo_url = "https://github.com/SwanHubX/SwanLab-Docs/tree/main/zh"
    base_html_url = "https://docs.swanlab.cn"
    github_token = "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"  # 替换为你的GitHub Token，或留空
    scrape_web_docs(repo_url, base_html_url, github_token)


