# db_utils.py

import json
from pymongo import MongoClient


def get_mongo_client(mongodb_uri: str) -> MongoClient:
    """
    MongoDB URI를 받아 MongoClient를 생성하여 반환합니다.
    """
    return MongoClient(mongodb_uri)


def insert_documents(db_client: MongoClient, db_name: str, collection_name: str, documents: list) -> None:
    """
    지정된 MongoDB(db_name)의 collection_name에 documents(list of dict)를 삽입합니다.
    내부에 datetime 객체 등이 있을 경우, BSON 인코딩이 되지 않기 때문에
    JSON 직렬화를 거쳐 삽입하도록 합니다.

    :param db_client: MongoClient 객체
    :param db_name: 데이터베이스 이름 (예: "cloudtrail", "s3accesslog", "vpcflow")
    :param collection_name: 컬렉션 이름 (예: "2025-05-20_to_2025-05-22")
    :param documents: 삽입할 문서 리스트 (각각 dict)
    """
    if not documents:
        print(f"[DB] {db_name}.{collection_name} 에 삽입할 문서가 없습니다.")
        return

    db = db_client[db_name]
    coll = db[collection_name]

    # datetime이나 다른 non-serializable 객체가 있으면 json.dumps로 처리
    to_insert = []
    for doc in documents:
        to_insert.append(json.loads(json.dumps(doc, default=str)))

    try:
        coll.insert_many(to_insert)
        print(f"[DB] {db_name}.{collection_name} 에 {len(to_insert)}개 문서 삽입 완료.")
    except Exception as e:
        print(f"[DB ERROR] {db_name}.{collection_name} 삽입 실패: {e}")


from datetime import datetime, timedelta

def extract_dates_from_report_id(report_id: str):
    try:
        _, start_str, end_str = report_id.split("_")
        return start_str, end_str
    except:
        return None, None

def get_logs_by_report_id(mongodb_uri: str, report_id: str) -> list:
    """
    report_id로부터 start, end 날짜를 추출하여 각 DB에서 로그를 조회합니다.
    각 DB는 cloudtrail, vpcflow, s3accesslog이며, 컬렉션은 yyyy-mm-dd_to_yyyy-mm-dd 형식입니다.
    """
    client = get_mongo_client(mongodb_uri)
    start, end = extract_dates_from_report_id(report_id)
    if not start or not end:
        return []

    collection_name = f"{start[:4]}-{start[4:6]}-{start[6:]}_to_{end[:4]}-{end[4:6]}-{end[6:]}"
    db_names = ["cloudtrail", "vpcflow", "s3accesslog"]
    all_logs = []

    for db_name in db_names:
        db = client[db_name]
        coll = db[collection_name]
        logs = list(coll.find({}, {"_id": 0}))
        for log in logs:
            log["log_type"] = db_name
        all_logs.extend(logs)

    return all_logs