import json
import os
import logging

# Configure logging  拼接json文件中分块的内容
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("extract_content.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def extract_fields_to_txt(json_file_path: str, output_txt_path: str = "extracted_fields.txt"):
    """
    从JSON文件中提取content、url和path字段到文本文件
    格式示例：
    [URL] https://example.com/path
    [PATH] /some/path (如果存在)
    [CONTENT] 这里是内容文本...
    ---分隔线---
    """
    try:
        # Read JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Open output file
        with open(output_txt_path, 'w', encoding='utf-8') as f:
            for doc in data.get('documents', []):
                # 获取字段（path为可选）
                content = doc.get('content', '')
                url = doc.get('url', '')
                html_url = doc.get('html_url', '')
                filename = doc.get('filename', 'unknown.md')

                if not content:
                    logging.warning(f"Empty content in document: {filename}")
                    continue

                # 写入提取的字段
                f.write(f"[CONTENT] \n{content}\n")
                f.write(f"[URL] {url}\n")
                f.write(f"[html_url] {html_url}\n")
                f.write("#########################\n\n")  # 文档间分隔

                logging.info(f"Processed: {filename} (URL: {url})")

        logging.info(f"Successfully created {output_txt_path}")

    except FileNotFoundError:
        logging.error(f"JSON file not found: {json_file_path}")
    except json.JSONDecodeError:
        logging.error(f"Invalid JSON format in {json_file_path}")
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    json_file_path = 'swanlab-1.json'  #选择你的json文件
    output_txt_path = 'swanlab.txt'    #保存到的地址
    extract_fields_to_txt(json_file_path, output_txt_path)