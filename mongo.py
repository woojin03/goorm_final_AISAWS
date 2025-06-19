# mongo.py
'''
from pymongo import MongoClient

# MongoDB 연결
uri = "mongodb+srv://admin:admin@cluster0.4bnwrsl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)

# 확인 대상 DB 및 컬렉션 이름
targets = {
    "cloudtrail": "2025-05-23_to_2025-05-23",
    "vpcflow": "2025-05-23_to_2025-05-23",
    "s3accesslog": "2025-05-23_to_2025-05-23",
}

for db_name, col_name in targets.items():
    print(f"\n📁 DB: {db_name}, 📦 컬렉션: {col_name}")
    db = client[db_name]
    col = db[col_name]

    # 샘플 로그 5개 출력
    docs = col.find().limit(2)
    for i, doc in enumerate(docs, 1):
        print(f"\n📝 문서 {i}")
        for k, v in doc.items():
            value_str = str(v)
            print(f"  {k}: {value_str[:200]}{'...' if len(value_str) > 200 else ''}")

'''

#- cloudtrail
# - s3accesslog
# - vpcflow
'''
from pymongo import MongoClient

# MongoDB Atlas 연결 URI
uri = "mongodb+srv://admin:admin@cluster0.4bnwrsl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

# 클라이언트 연결
client = MongoClient(uri)

# DB 목록 출력
print("📁 [1] 데이터베이스 목록:")
for db_name in client.list_database_names():
    print(f" - {db_name}")

# 특정 DB 이름을 수동 설정하거나, 첫 번째 DB 선택 (예시: 'Cluster0')
db_name = "cloudtrail"
db = client[db_name]

# 컬렉션 목록 출력
print(f"\n📦 [2] '{db_name}' 내 컬렉션 목록:")
for col_name in db.list_collection_names():
    print(f" - {col_name}")


'''

#- cloudtrail
# - s3accesslog
# - vpcflow

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["cloudtrail"]  # ✅ cloudtrail DB 선택

# 삭제할 컬렉션 목록
collections_to_delete = [
    "2025-06-09_to_2025-06-09",

]

for name in collections_to_delete:
    if name in db.list_collection_names():
        db.drop_collection(name)
        print(f"✅ 컬렉션 삭제 완료: {name}")
    else:
        print(f"⚠️ 존재하지 않음: {name}")
