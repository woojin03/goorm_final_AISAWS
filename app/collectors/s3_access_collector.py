# collectors/s3_access_collector.py

import gzip
import io
import shlex
import re
from datetime import datetime, timedelta
import boto3
import geoip2.database
import os
from typing import Optional

_geoip_reader = None
_ip_country_cache: dict[str, Optional[str]] = {}

def get_geoip_reader():
    """
    1) GEOLITE2_DB_PATH 환경 변수에서 상대경로(또는 절대경로)를 읽어옵니다.
    2) 절대경로가 아니라면, 현재 작업 디렉터리(os.getcwd())를 기준으로 절대경로로 변환합니다.
    3) 한 번만 geoip2.database.Reader를 생성하여 _geoip_reader에 보관합니다.
    """
    global _geoip_reader
    if _geoip_reader is None:
        geoip_path = os.getenv("GEOLITE2_DB_PATH")
        if not geoip_path:
            raise RuntimeError("환경 변수 GEOLITE2_DB_PATH가 설정되지 않았습니다.")
        # 상대경로 → 절대경로로 변환
        if not os.path.isabs(geoip_path):
            geoip_path = os.path.join(os.getcwd(), geoip_path)
        _geoip_reader = geoip2.database.Reader(geoip_path)
    return _geoip_reader

def lookup_country(ip_addr: Optional[str]) -> Optional[str]:
    """
    주어진 IP에 대해 캐시를 먼저 확인하고, 없으면 GeoIP Reader로 조회 후 캐시합니다.
    조회된 ISO country code(예: "US", "KR")를 반환하며, 실패 시 None 반환.
    """
    if not ip_addr:
        return None
    if ip_addr in _ip_country_cache:
        return _ip_country_cache[ip_addr]
    try:
        reader = get_geoip_reader()
        match = reader.country(ip_addr)
        country_code = match.country.iso_code if (match and match.country.iso_code) else None
    except Exception:
        country_code = None
    _ip_country_cache[ip_addr] = country_code
    return country_code

def get_boto3_session(access_key: str, secret_key: str, region: str):
    """
    AWS 자격증명을 받아 Boto3 세션을 반환합니다.
    """
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )


def parse_s3_log_line(line: str) -> Optional[dict]:
    parts = shlex.split(line)
    if len(parts) < 18:
        return None

    def to_int(x):
        try:
            return int(x)
        except:
            return x

    time_raw = parts[2]
    # +0000이 parts[3]에 잘못 붙은 경우 고려
    if time_raw.startswith("[") and parts[3].startswith("+"):
        time_combined = f"{time_raw} {parts[3]}"
        try:
            dt = datetime.strptime(time_combined.strip("[]"), "%d/%b/%Y:%H:%M:%S %z")
            iso_time = dt.isoformat()
        except:
            iso_time = time_raw
    else:
        iso_time = time_raw


    remote_ip = parts[3]
    requester = parts[4]

    # remote_ip가 잘못된 경우에만 requester의 IP를 대체로 사용
    if remote_ip.startswith("+") or remote_ip == "-":
        remote_ip = requester if re.match(r"\d+\.\d+\.\d+\.\d+", requester) else None


    user_agent = parts[16] if parts[16] != "-" else None
    version_id = parts[17] if parts[17] != "-" else None
    if version_id and version_id.startswith("Mozilla"):
        user_agent = version_id
        version_id = None

    return {
        "bucket_owner": parts[0],
        "bucket": parts[1],
        "time": iso_time,
        "remote_ip": remote_ip,
        "requester": requester,
        "request_id": parts[5],
        "operation": parts[6],
        "key": parts[7] if parts[7] != "-" else None,
        "request_uri": parts[8],
        "http_status": parts[9],
        "status_code": parts[10] if parts[10] != "-" else None,
        "bytes_sent": to_int(parts[11]),
        "object_size": to_int(parts[12]),
        "total_time": to_int(parts[13]),
        "turnaround_time": to_int(parts[14]),
        "referrer": parts[15] if parts[15] != "-" else None,
        "user_agent": user_agent,
        "version_id": version_id
    }

def collect_s3_access_logs(access_key: str, secret_key: str, region: str,
                           bucket_name: str, prefix: str,
                           start_date_str: str, end_date_str: str, log_messages: list) -> list:
    """
    지정된 S3 버킷(bucket_name)에서 Access Log 파일들을 날짜 필터링 후 다운로드하여,
    한 줄씩 parse_s3_log_line을 거쳐 파싱된 레코드 리스트를 반환합니다.

    :param access_key: AWS ACCESS_KEY
    :param secret_key: AWS SECRET_KEY
    :param region: AWS REGION
    :param bucket_name: Access Log가 저장된 S3 버킷명
    :param prefix: S3 버킷 내 접두사 (예: "logs/s3/")
    :param start_date_str: 시작 날짜 (YYYY-MM-DD)
    :param end_date_str: 종료 날짜 (YYYY-MM-DD)
    :return: 파싱된 레코드 딕셔너리 리스트
    """
    try:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        # 포함되지 않도록 하루 더함
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        raise ValueError("S3 AccessLog 날짜 형식 오류: YYYY-MM-DD 형태로 입력해야 합니다.")

    log_messages.append(f"[+] 로그 수집 기간: {start_dt} ~ {end_dt}")

    session = get_boto3_session(access_key, secret_key, region)
    s3 = session.client("s3")

    paginator = s3.get_paginator("list_objects_v2")
    log_messages.append(f"[*] S3 버킷에서 객체 목록을 조회 중... ({bucket_name})")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    parsed_records = []
    log_messages.append("[*] 로그 파일 필터링 및 수집 시작...\n")
    count = 0
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]

            # Key 안에서 YYYY-MM-DD 패턴을 찾아 날짜 판별
            m = re.search(r"(\d{4}-\d{2}-\d{2})", key)
            if not m:
                continue

            try:
                log_date = datetime.strptime(m.group(1), "%Y-%m-%d")
            except:
                continue

            if not (start_dt <= log_date < end_dt):
                continue

            # 대상 파일 다운로드
            count += 1
            resp = s3.get_object(Bucket=bucket_name, Key=key)
            raw_data = resp["Body"].read()
            if key.endswith(".gz"):
                with gzip.GzipFile(fileobj=io.BytesIO(raw_data)) as gz:
                    body = gz.read().decode("utf-8")
            else:
                body = raw_data.decode("utf-8")

            # 한 줄씩 파싱
            for line in body.splitlines():
                if not line.strip():
                    continue
                rec = parse_s3_log_line(line)
                if not rec:
                    continue

                ip_addr = rec.get("requester")
                rec["country"] = lookup_country(ip_addr)

                parsed_records.append(rec)
                
        log_messages.append(f"[+] 총 수집된 로그 파일 수: {count}")
    return parsed_records
