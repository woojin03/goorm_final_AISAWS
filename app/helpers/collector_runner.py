# app/helpers/collector_runner.py

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from app.collectors.cloudtrail_collector import collect_cloudtrail_events
from app.collectors.s3_access_collector import collect_s3_access_logs
from app.collectors.vpc_flow_collector import collect_vpc_flow_logs
from app.helpers.db_utils import get_mongo_client, insert_documents

'''
def save_logs_to_file(filename: str, logs: list):
    path = Path("logs")
    path.mkdir(parents=True, exist_ok=True)
    with open(path / filename, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
'''
        

def run_collectors_stream(start_date: str, end_date: str):
    load_dotenv()

    ACCESS_KEY = os.getenv("ACCESS_KEY")
    SECRET_KEY = os.getenv("SECRET_KEY")
    REGION = os.getenv("REGION")

    S3_BUCKET = os.getenv("S3_ACCESS_LOG_BUCKET")
    S3_PREFIX = os.getenv("S3_ACCESS_LOG_PREFIX", "")
    VPC_BUCKET = os.getenv("VPC_FLOW_LOG_BUCKET")
    VPC_PREFIX = os.getenv("VPC_FLOW_LOG_PREFIX", "")
    MONGODB_URI = os.getenv("MONGODB_URI")

    collection_name = f"{start_date}_to_{end_date}"
    mongo_client = get_mongo_client(MONGODB_URI)

    yield "\n>>> [Step 1] S3 Access Log 수집 시작\n"
    s3_logs = collect_s3_access_logs(
        ACCESS_KEY, SECRET_KEY, REGION,
        S3_BUCKET, S3_PREFIX,
        start_date, end_date,
        log_messages := []
    )
    for msg in log_messages:
        yield msg + "\n"
    insert_documents(mongo_client, "s3accesslog", collection_name, s3_logs)
    #save_logs_to_file(f"s3accesslog.{collection_name}.json", s3_logs)
    yield f"[DB] s3accesslog.{collection_name} 에 {len(s3_logs)}개 문서 삽입 완료.\n"

    yield "\n>>> [Step 2] VPC Flow Log 수집 시작\n"
    vpc_logs = collect_vpc_flow_logs(
        ACCESS_KEY, SECRET_KEY, REGION,
        VPC_BUCKET, VPC_PREFIX,
        start_date, end_date,
        log_messages := []
    )
    for msg in log_messages:
        yield msg + "\n"
    insert_documents(mongo_client, "vpcflow", collection_name, vpc_logs)
    #save_logs_to_file(f"vpcflow.{collection_name}.json", vpc_logs)
    yield f"[DB] vpcflow.{collection_name} 에 {len(vpc_logs)}개 문서 삽입 완료.\n"

    yield "\n>>> [Step 3] CloudTrail 이벤트 수집 시작\n"
    ct_logs = collect_cloudtrail_events(
        ACCESS_KEY, SECRET_KEY, REGION,
        start_date, end_date,
        log_messages := []
    )
    for msg in log_messages:
        yield msg + "\n"
    insert_documents(mongo_client, "cloudtrail", collection_name, ct_logs)
    #save_logs_to_file(f"cloudtrail.{collection_name}.json", ct_logs)
    yield f"[DB] cloudtrail.{collection_name} 에 {len(ct_logs)}개 문서 삽입 완료.\n"

    yield "\n=== ✅ 모든 로그 수집 및 MongoDB 저장 완료 ===\n"
