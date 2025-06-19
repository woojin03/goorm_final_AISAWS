# collectors/vpc_flow_collector.py

import gzip
import io
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


def collect_vpc_flow_logs(access_key: str, secret_key: str, region: str,
                          bucket_name: str, prefix: str,
                          start_date_str: str, end_date_str: str, 
                          log_messages: list) -> list:
    """
    지정된 S3 버킷(bucket_name)에서 VPC Flow Log 파일을 날짜별 경로(YYYY/MM/DD)
    기준으로 필터링 후 다운로드하여, 각 줄을 파싱해 딕셔너리 리스트로 반환합니다.
    (한 줄 당 14개 필드: version, account-id, interface-id, srcaddr, dstaddr,
     srcport, dstport, protocol, packets, bytes, start, end, action, log-status)

    :param access_key: AWS ACCESS_KEY
    :param secret_key: AWS SECRET_KEY
    :param region: AWS REGION
    :param bucket_name: VPC Flow Log가 저장된 S3 버킷명
    :param prefix: S3 버킷 내 접두사 (예: "logs/vpc/")
    :param start_date_str: 시작 날짜 (YYYY-MM-DD)
    :param end_date_str: 종료 날짜 (YYYY-MM-DD)
    :return: 파싱된 레코드 딕셔너리 리스트
    """
    try:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        raise ValueError("VPC FlowLog 날짜 형식 오류: YYYY-MM-DD 형태로 입력해야 합니다.")
    log_messages.append(f"[+] 로그 수집 기간: {start_dt} ~ {end_dt}")

    session = get_boto3_session(access_key, secret_key, region)
    s3 = session.client("s3")

    paginator = s3.get_paginator("list_objects_v2")
    log_messages.append(f"[*] S3 버킷에서 객체 목록을 조회 중... ({bucket_name})")
    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

    parsed_records = []
    count = 0
    log_messages.append("[*] 로그 파일 필터링 및 수집 시작...\n")

    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            parts = key.split("/")
            if len(parts) < 4:
                continue

            # 뒤에서부터 YYYY/MM/DD 형태를 파싱
            try:
                year = int(parts[-5])
                month = int(parts[-4])
                day = int(parts[-3])
                log_date = datetime(year, month, day)
            except:
                continue

            if not (start_dt <= log_date < end_dt):
                continue

            count += 1
            # 대상 파일 다운로드
            resp = s3.get_object(Bucket=bucket_name, Key=key)
            raw_data = resp["Body"].read()
            with gzip.GzipFile(fileobj=io.BytesIO(raw_data)) as gz:
                content = gz.read().decode("utf-8")

            # 각 줄 파싱 (14개 필드)
            for line in content.splitlines():
                if not line.strip():
                    continue
                if line.startswith("version") or line.startswith("Version"):
                    # 헤더가 있으면 스킵
                    continue

                fields = line.split()
                if len(fields) < 14:
                    continue

                try:
                    rec = {
                        "version": fields[0],
                        "account_id": fields[1],
                        "interface_id": fields[2],
                        "srcaddr": fields[3],
                        "dstaddr": fields[4],
                        "srcport": int(fields[5]),
                        "dstport": int(fields[6]),
                        "protocol": fields[7],
                        "packets": int(fields[8]),
                        "bytes": int(fields[9]),
                        "start": int(fields[10]),
                        "end": int(fields[11]),
                        "action": fields[12],
                        "log_status": fields[13]
                    }
                except:
                    continue

                # ── GeoIP 조회 (캐시 적용) ─────────────────────────
                ip_addr = rec.get("srcaddr")
                rec["country"] = lookup_country(ip_addr)
                # ─────────────────────────────────────────────────

                parsed_records.append(rec)
        log_messages.append(f"[+] 총 수집된 로그 파일 수: {count}")

    return parsed_records
