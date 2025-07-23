import requests
import time
import json
import os
from datetime import datetime

# 飞书应用配置（替换为你的实际配置）
APP_ID = "cli_a81b173e2c72501c"  # 你的App ID
APP_SECRET = "DqcJ53z8d2fk30Cy9mM7Ch0FGfrYtsYh"  # 你的App Secret
APP_TOKEN = "V1EqbKusVarKHEsryFhcccpvnng"  # 多维表格ID（从URL获取）
TABLE_ID = "tblKtI36id8ZWRN8"  # 数据表ID（从URL获取）
VIEW_ID = "vew28o6unZ"  # 视图ID（可选，用于过滤数据）

# JSON文件保存路径
JSON_FILE_PATH = "feishu_qa_data.json"

# API基础URL
BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuQAExtractor:
    def __init__(self):
        self.access_token = None
        self.token_expire_time = 0
        self.last_modified_time = "2025-08-09T00:00:00.000Z"  # 初始时间
        self.qa_data = {}  # 存储所有QA数据 {record_id: {编号, 问题, 答案, modified_time}}

        # 如果JSON文件存在，加载现有数据
        self.load_existing_data()

    def load_existing_data(self):
        """加载已存在的JSON数据"""
        if os.path.exists(JSON_FILE_PATH):
            try:
                with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.qa_data = data.get('qa_data', {})
                    self.last_modified_time = data.get('last_modified_time', "1970-01-01T00:00:00.000Z")
                    print(f"已加载现有数据，共 {len(self.qa_data)} 条记录")
                    print(f"最后更新时间: {self.last_modified_time}")
            except Exception as e:
                print(f"加载JSON文件失败: {str(e)}")
                self.qa_data = {}

    def save_to_json(self):
        """保存数据到JSON文件"""
        data = {
            'last_modified_time': self.last_modified_time,
            'update_time': datetime.now().isoformat(),
            'qa_data': self.qa_data
        }

        try:
            with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"数据已保存到 {JSON_FILE_PATH}")
        except Exception as e:
            print(f"保存JSON文件失败: {str(e)}")

    def get_access_token(self):
        """获取访问令牌"""
        url = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": APP_ID,
            "app_secret": APP_SECRET
        }

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 0:
                self.access_token = data["tenant_access_token"]
                self.token_expire_time = time.time() + data["expire"] - 300  # 提前5分钟刷新
                print(f"成功获取访问令牌，有效期至: {datetime.fromtimestamp(self.token_expire_time)}")
                return True
            else:
                print(f"获取访问令牌失败: {data.get('msg')}")
                return False
        except Exception as e:
            print(f"请求访问令牌时出错: {str(e)}")
            return False

    def ensure_token_valid(self):
        """确保访问令牌有效"""
        if not self.access_token or time.time() >= self.token_expire_time:
            return self.get_access_token()
        return True

    def get_all_records(self, page_size=100):
        """获取所有记录（不带任何过滤或排序）"""
        if not self.ensure_token_valid():
            return None

        url = f"{BASE_URL}/bitable/v1/apps/{APP_TOKEN}/tables/{TABLE_ID}/records"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        params = {
            "page_size": page_size
        }

        # 如果有视图ID，添加到参数中
        if VIEW_ID:
            params["view_id"] = VIEW_ID

        all_records = []
        page_token = ""

        try:
            while True:
                if page_token:
                    params["page_token"] = page_token

                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()

                if data.get("code") != 0:
                    print(f"获取数据失败: {data.get('msg')}")
                    return None

                items = data.get("data", {}).get("items", [])
                all_records.extend(items)

                # 调试信息：打印第一条记录的结构
                if items and len(all_records) == len(items):
                    print("调试信息：第一条记录结构:")
                    print(json.dumps(items[0], indent=2, ensure_ascii=False))

                page_token = data.get("data", {}).get("page_token")
                if not page_token:
                    break

            return all_records
        except Exception as e:
            print(f"获取所有记录时出错: {str(e)}")
            return None

    def extract_record_data(self, item):
        """从API返回项中提取记录数据，处理不同的数据结构"""
        # 检查是否有嵌套的 "record" 键
        if "record" in item:
            return item["record"]
        # 如果没有 "record" 键，假设 item 本身就是记录数据
        elif "record_id" in item and "fields" in item:
            return item
        # 如果都不匹配，打印调试信息并返回 None
        else:
            print("调试信息：无法识别的记录结构:")
            print(json.dumps(item, indent=2, ensure_ascii=False))
            return None

    def filter_records_by_time(self, records):
        """在本地根据修改时间过滤记录"""
        if not records:
            return []

        # 将时间字符串转换为datetime对象进行比较
        try:
            last_modified_dt = datetime.fromisoformat(self.last_modified_time.replace('Z', '+00:00'))
        except:
            # 如果转换失败，使用初始时间
            last_modified_dt = datetime(1970, 1, 1)

        filtered_records = []

        for item in records:
            # 提取记录数据
            record = self.extract_record_data(item)
            if record is None:
                continue

            modified_time = record.get("modified_time", "")

            try:
                modified_dt = datetime.fromisoformat(modified_time.replace('Z', '+00:00'))
                if modified_dt > last_modified_dt:
                    filtered_records.append(item)
            except:
                # 如果时间格式解析失败，默认包含该记录
                filtered_records.append(item)

        # 更新最后修改时间
        if filtered_records:
            latest_record = None
            latest_time = last_modified_dt

            for item in filtered_records:
                record = self.extract_record_data(item)
                if record is None:
                    continue

                modified_time = record.get("modified_time", "")
                try:
                    modified_dt = datetime.fromisoformat(modified_time.replace('Z', '+00:00'))
                    if modified_dt > latest_time:
                        latest_time = modified_dt
                        latest_record = record
                except:
                    pass

            if latest_record:
                self.last_modified_time = latest_record.get("modified_time", self.last_modified_time)

        return filtered_records

    def process_qa_records(self, records):
        """处理QA记录"""
        if not records:
            print("没有新数据")
            return 0

        print(f"\n发现 {len(records)} 条新记录 (最后更新时间: {self.last_modified_time})")
        print("-" * 50)

        updated_count = 0

        for item in records:
            # 提取记录数据
            record = self.extract_record_data(item)
            if record is None:
                continue

            record_id = record.get("record_id")
            fields = record.get("fields", {})

            # 提取我们需要的字段
            qa_entry = {
                "编号": fields.get("编号", ""),
                "问题": fields.get("问题", ""),
                "答案": fields.get("答案", ""),
                "modified_time": record.get("modified_time")
            }

            # 更新或添加记录
            if record_id in self.qa_data:
                # 检查内容是否有变化
                old_entry = self.qa_data[record_id]
                if (old_entry["编号"] != qa_entry["编号"] or
                        old_entry["问题"] != qa_entry["问题"] or
                        old_entry["答案"] != qa_entry["答案"]):
                    print(f"更新记录 ID: {record_id}")
                    self.qa_data[record_id] = qa_entry
                    updated_count += 1
            else:
                print(f"新增记录 ID: {record_id}")
                self.qa_data[record_id] = qa_entry
                updated_count += 1

            # 打印记录信息
            print(f"编号: {qa_entry['编号']}")
            print(f"问题: {qa_entry['问题']}")
            print(f"答案: {qa_entry['答案']}")
            print("-" * 30)

        return updated_count

    def run_polling(self, interval=30):
        """运行轮询监听"""
        print("开始监听飞书多维表格QA数据更新...")
        print(f"轮询间隔: {interval}秒")
        print(f"数据将保存到: {JSON_FILE_PATH}")

        while True:
            try:
                # 获取所有记录
                all_records = self.get_all_records()
                if all_records is not None:
                    # 在本地过滤新记录
                    new_records = self.filter_records_by_time(all_records)
                    updated_count = self.process_qa_records(new_records)
                    if updated_count > 0:
                        self.save_to_json()

                time.sleep(interval)
            except KeyboardInterrupt:
                print("\n停止监听")
                break
            except Exception as e:
                print(f"运行时出错: {str(e)}")
                time.sleep(interval)


if __name__ == "__main__":
    extractor = FeishuQAExtractor()
    extractor.run_polling(interval=30)  # 每30秒检查一次更新