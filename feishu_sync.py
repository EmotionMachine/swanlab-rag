# 飞书应用配置（替换为你的实际配置）
APP_ID = "cli_a81b173e2c72501c"  # 你的App ID
APP_SECRET = "DqcJ53z8d2fk30Cy9mM7Ch0FGfrYtsYh"  # 你的App Secret
APP_TOKEN = "V1EqbKusVarKHEsryFhcccpvnng"  # 多维表格ID（从URL获取）
TABLE_ID = "tblKtI36id8ZWRN8"  # 数据表ID（从URL获取）
VIEW_ID = "vew28o6unZ"  # 视图ID（可选，用于过滤数据）

# feishu_sync.py
import requests
import time
import json
# --- 请在这里填入您的飞书应用信息 ---
FEISHU_APP_ID = "cli_a81b173e2c72501c"  # 替换为你的 App ID
FEISHU_APP_SECRET = "DqcJ53z8d2fk30Cy9mM7Ch0FGfrYtsYh"  # 替换为你的 App Secret
BASE_APP_TOKEN = "V1EqbKusVarKHEsryFhcccpvnng"  # 替换为你的 Base App Token
TABLE_ID = "tblMStdOJrn7y531"  # 替换为你的 Table ID
# ------------------------------------

# 用于缓存 token
feishu_token_cache = {
    "token": None,
    "expire_time": 0
}


def get_feishu_tenant_access_token():
    """获取或刷新飞书 tenant_access_token"""
    now = time.time()
    if feishu_token_cache["token"] and now < feishu_token_cache["expire_time"]:
        return feishu_token_cache["token"]

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    payload = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()

        feishu_token_cache["token"] = data["tenant_access_token"]
        feishu_token_cache["expire_time"] = now + data.get("expire", 7200) - 300
        print("成功获取飞书 tenant_access_token")
        return data["tenant_access_token"]
    except requests.exceptions.RequestException as e:
        print(f"获取飞书 token 失败: {e}")
        return None


def find_record_by_question_id(question_id: int):
    """通过 question_id 查找飞书表格中的记录，返回 record_id"""
    token = get_feishu_tenant_access_token()
    if not token:
        return None

    # 构建带过滤条件的URL
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_TOKEN}/tables/{TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "filter": f'CurrentValue.[question_id] = "{question_id}"',
        "page_size": 1
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", {})
        items = data.get("items", [])
        if items:
            record_id = items[0]["record_id"]
            print(f"找到已存在的记录, question_id: {question_id}, record_id: {record_id}")
            return record_id
        return None
    except requests.exceptions.RequestException as e:
        print(f"查询飞书记录失败: {e.response.text if e.response else e}")
        return None


def sync_data_to_feishu(data: dict):
    """将数据同步到飞书，如果记录存在则更新，不存在则创建"""
    token = get_feishu_tenant_access_token()
    if not token:
        return

    question_id = data.get("question_id")
    if not question_id:
        print("同步失败：数据中缺少 question_id")
        return

    record_id = find_record_by_question_id(question_id)

    # 格式化数据以匹配飞书 API 要求
    payload = {"fields": data}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print("---即将发送到飞书的数据---")
    # 使用 json.dumps 打印，格式更清晰，且能暴露无法序列化的对象
    try:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    except TypeError as e:
        print(f"数据序列化失败: {e}")
        print("原始数据:", payload)
    print("--------------------------")
    # ---------------------------

    try:
        if record_id:
            # 更新记录
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_TOKEN}/tables/{TABLE_ID}/records/{record_id}"
            response = requests.put(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            print(f"成功更新飞书记录, record_id: {record_id}")
        else:
            # 创建新记录
            url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_APP_TOKEN}/tables/{TABLE_ID}/records"
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            print(f"成功创建飞书记录, question_id: {question_id}")

    except requests.exceptions.RequestException as e:
        print(f"同步数据到飞书失败: {e.response.text if e.response else e}")