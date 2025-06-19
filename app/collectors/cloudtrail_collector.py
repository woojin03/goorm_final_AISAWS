# collectors/cloudtrail_collector.py

import json
from datetime import datetime, timedelta
import boto3
import geoip2.database
import os
from typing import Optional  # ✅ 추가

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
        # 상대경로 → 절대경로 변환
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


def collect_cloudtrail_events(access_key: str, secret_key: str, region: str,
                              start_date_str: str, end_date_str: str, log_messages: list) -> list:
    """
    CloudTrail lookup_events API를 호출하여 주어진 날짜 범위(start_date ~ end_date) 동안의 이벤트를
    가져와 JSON 리스트로 반환합니다.

    :param access_key: AWS ACCESS_KEY
    :param secret_key: AWS SECRET_KEY
    :param region: AWS REGION
    :param start_date_str: 시작 날짜 (YYYY-MM-DD)
    :param end_date_str: 종료 날짜 (YYYY-MM-DD)
    :return: 이벤트 JSON 객체 리스트
    """
    try:
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        # end_date는 범위에 포함되지 않도록 하루 더함
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        raise ValueError("날짜 형식 오류: YYYY-MM-DD 형태로 입력해야 합니다.")

    log_messages.append(f"[+] 로그 수집 기간: {start_dt} ~ {end_dt}")

    session = get_boto3_session(access_key, secret_key, region)
    client = session.client("cloudtrail")

    log_messages.append("[*] CloudTrail에서 이벤트를 조회 중입니다...")

    events = []
    next_token = None
    batch_count = 0
    while True:
        if next_token:
            resp = client.lookup_events(
                StartTime=start_dt,
                EndTime=end_dt,
                MaxResults=50,
                NextToken=next_token
            )
        else:
            resp = client.lookup_events(
                StartTime=start_dt,
                EndTime=end_dt,
                MaxResults=50
            )

        batch = resp.get("Events", [])
        events.extend(batch)

        next_token = resp.get("NextToken")
        if not next_token:
            break

    log_messages.append(f"[+] 총 이벤트 수: {len(events)}건\n")

    enriched_events: list[dict] = []
    for ev in events:
        ev_copy = ev.copy()
        ip_addr = None
        raw_str = ev_copy.get("CloudTrailEvent")
        if raw_str:
            try:
                obj = json.loads(raw_str)
                ip_addr = obj.get("sourceIPAddress")

                # Username이 AISAWS인 경우 수집 제외
                if obj.get("userIdentity", {}).get("userName") == "AISAWS":
                    continue

            except Exception:
                ip_addr = None

        # lookup_country()로 국가 코드 계산 후 최상위 필드에 저장
        ev_copy["country"] = lookup_country(ip_addr)
        enriched_events.append(ev_copy)

    log_messages.append(f"[+] 필터링 후 저장 대상 이벤트 수: {len(enriched_events)}건\n")
    return enriched_events