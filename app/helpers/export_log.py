# export_log.py

import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

# ✅ 환경 변수에서 Mongo URI 불러오기
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")  # fallback for dev

# ✅ JSON 직렬화 대응
def convert_for_json(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_for_json(item) for item in obj]
    else:
        return obj

# ✅ 시간 필드 매핑
SORT_FIELDS = {
    "cloudtrail": "EventTime",
    "vpcflow": "start",
    "s3accesslog": "time"
}

# ✅ 메인 함수
def export_logs(start: str, end: str) -> dict:
    try:
        client = MongoClient(MONGODB_URI)
        client.admin.command('ping')  # 연결 확인
    except ConnectionFailure as e:
        print(f"❌ MongoDB 연결 실패: {e}")
        return {}

    collection_name = f"{start}_to_{end}"
    log_sources = ["cloudtrail", "vpcflow", "s3accesslog"]
    logs = {}

    for db_name in log_sources:
        try:
            db = client[db_name]
            collection = db[collection_name]
            sort_field = SORT_FIELDS.get(db_name, None)

            if sort_field:
                cursor = collection.find({}, {"_id": 0}).sort(sort_field, 1)  # 오름차순 정렬
            else:
                cursor = collection.find({}, {"_id": 0})  # 정렬 필드가 없을 경우

            result = list(cursor)
            logs[db_name] = convert_for_json(result)
            print(f"✅ {db_name}.{collection_name} → {len(result)}건 수집")
        except Exception as e:
            print(f"⚠️ {db_name}.{collection_name} → 수집 실패: {e}")
            logs[db_name] = []

    return logs



'''
import json
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from datetime import datetime
import os
from dotenv import load_dotenv

# ✅ 환경 변수에서 Mongo URI 불러오기
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# ✅ JSON 직렬화 대응
def convert_for_json(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_for_json(item) for item in obj]
    else:
        return obj

# ✅ 시간 필드 매핑
SORT_FIELDS = {
    "cloudtrail": "EventTime",
    "vpcflow": "start",
    "s3accesslog": "time"
}

# ✅ 메인 함수
def export_logs(start: str, end: str) -> dict:
    try:
        client = MongoClient(MONGODB_URI)
        client.admin.command('ping')  # 연결 확인
    except ConnectionFailure as e:
        print(f"❌ MongoDB 연결 실패: {e}")
        return {}

    collection_name = f"{start}_to_{end}"
    log_sources = ["cloudtrail", "vpcflow", "s3accesslog"]
    logs = {}

    for db_name in log_sources:
        try:
            db = client[db_name]
            collection = db[collection_name]
            sort_field = SORT_FIELDS.get(db_name)

            if sort_field:
                cursor = collection.find({}, {"_id": 0}).sort(sort_field, 1)
            else:
                cursor = collection.find({}, {"_id": 0})

            result = list(cursor)

            # ✅ CloudTrailEvent 문자열 → dict 복원
            if db_name == "cloudtrail":
                for doc in result:
                    if "CloudTrailEvent" in doc and isinstance(doc["CloudTrailEvent"], str):
                        try:
                            doc["CloudTrailEvent"] = json.loads(doc["CloudTrailEvent"])
                        except json.JSONDecodeError:
                            print("⚠️ CloudTrailEvent 파싱 실패:", doc.get("EventId"))

            logs[db_name] = convert_for_json(result)
            print(f"✅ {db_name}.{collection_name} → {len(result)}건 수집")

        except Exception as e:
            print(f"⚠️ {db_name}.{collection_name} → 수집 실패: {e}")
            logs[db_name] = []

    return logs
'''