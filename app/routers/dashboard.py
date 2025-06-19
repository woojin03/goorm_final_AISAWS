# app/routers/dashboard.py

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
from collections import Counter
import urllib.parse
import os
from dotenv import load_dotenv
import aiohttp
from fastapi import APIRouter, UploadFile, File

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# .env에서 MongoDB URI 로드
load_dotenv()
MONGO_URI = os.getenv("MONGODB_URI")
if not MONGO_URI:
    raise RuntimeError("환경 변수 MONGODB_URI가 설정되지 않았습니다.")
client = AsyncIOMotorClient(MONGO_URI)

db_cloudtrail = client["cloudtrail"]
db_vpc = client["vpcflow"]
db_s3 = client["s3accesslog"]

# 현재 선택된 컬렉션
current_collection = {
    "cloudtrail": "2025-05-23_to_2025-05-23",
    "vpcflow": "2025-05-23_to_2025-05-23",
    "s3accesslog": "2025-06-09_to_2025-06-09"
}

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, collection: str = None):
    if collection:
        current_collection["cloudtrail"] = collection
        current_collection["vpcflow"] = collection
        current_collection["s3accesslog"] = collection
        print(f"✅ 컬렉션 변경됨: {collection}")
    return templates.TemplateResponse("dashboard.html", {"request": request, "page": "dashboard"})

@router.post("/api/set-collection")
async def set_collection(
    cloudtrail: str = Query(...),
    vpcflow: str = Query(...),
    s3accesslog: str = Query(...)
):
    current_collection["cloudtrail"] = cloudtrail
    current_collection["vpcflow"] = vpcflow
    current_collection["s3accesslog"] = s3accesslog
    return {"message": "✅ 컬렉션 설정 완료", "selected": current_collection}

@router.get("/api/collections/cloudtrail")
async def list_cloudtrail_collections():
    collections = await db_cloudtrail.list_collection_names()
    print(f"📁 클라우드트레일 컬렉션 목록 ({len(collections)}개):")
    for i, name in enumerate(collections, 1):
        print(f"{i}. {name}")
    return JSONResponse(content={"collections": collections})

@router.get("/api/chart1")
async def chart1():
    docs = await db_cloudtrail[current_collection["cloudtrail"]].find({}, {"EventTime": 1, "_id": 0}).to_list(None)
    return JSONResponse([doc["EventTime"] for doc in docs if "EventTime" in doc])

@router.get("/api/chart2")
async def chart2():
    cursor = db_vpc[current_collection["vpcflow"]].aggregate([
        {"$group": {"_id": "$action", "count": {"$sum": 1}}}
    ])
    result = await cursor.to_list(None)
    return {doc["_id"]: doc["count"] for doc in result}

@router.get("/api/chart3")
async def chart3():
    cursor = db_s3[current_collection["s3accesslog"]].aggregate([
        {"$group": {"_id": "$status_code", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ])
    result = await cursor.to_list(None)
    print(f"🔎 error_code 고유값 목록 (총 {len(result)}종):")
    for i, doc in enumerate(result, 1):
        code = doc["_id"] if doc["_id"] not in (None, "") else "unknown"
        print(f"{i}. {repr(code)} - {doc['count']}건")
    return JSONResponse({str(doc["_id"] or "unknown"): doc["count"] for doc in result})

@router.get("/api/chart4")
async def chart4():
    cursor = db_vpc[current_collection["vpcflow"]].aggregate([
        {"$group": {"_id": "$srcaddr", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ])
    result = await cursor.to_list(None)
    return [{"ip": doc["_id"], "count": doc["count"]} for doc in result if doc["_id"]]

@router.get("/api/chart5")
async def get_encoded_request_uris_with_count():
    s3_col = db_s3[current_collection["s3accesslog"]]
    raw_docs = await s3_col.find(
        {"request_uri": {"$exists": True, "$ne": None}},
        {"_id": 0, "request_uri": 1}
    ).to_list(length=None)

    uris = []
    for doc in raw_docs:
        uri = doc.get("request_uri")
        if not isinstance(uri, str):
            continue
        uri = uri.strip()
        if uri.startswith("%") or (not uri.startswith("-") and not uri.startswith("%")):
            uris.append(uri)

    uri_counter = Counter(uris)
    result = []
    for encoded_uri, count in uri_counter.items():
        decoded_uri = urllib.parse.unquote(urllib.parse.unquote(encoded_uri))
        result.append({"original": encoded_uri, "decoded": decoded_uri, "count": count})
    result.sort(key=lambda x: x["count"], reverse=True)
    print(f"📦 유효한 request_uri만 출력 (총 {len(result)}건)")
    for i, item in enumerate(result[:5], 1):
        print(f"{i}. {item['decoded']} - {item['count']}회 다운로드")
    return JSONResponse(content=result)

@router.get("/api/chart6")
async def chart6():
    cursor = db_vpc[current_collection["vpcflow"]].aggregate([
        {"$group": {"_id": "$srcaddr", "unique_ports": {"$addToSet": "$dstport"}}},
        {"$project": {"srcaddr": "$_id", "num_ports": {"$size": "$unique_ports"}, "_id": 0}},
        {"$match": {"num_ports": {"$gte": 0}}},
        {"$sort": {"num_ports": -1}},
        {"$limit": 10}
    ])
    return await cursor.to_list(None)

@router.get("/api/chart7")
async def chart7():
    docs = await db_s3[current_collection["s3accesslog"]].find(
        {"country": {"$exists": True, "$ne": ""}},
        {"_id": 0, "country": 1}
    ).to_list(None)
    countries = [doc["country"] for doc in docs]
    counter = Counter(countries)
    print(f"🌍 국가별 요청 수 (총 {len(counter)}개국):")
    for country, count in counter.items():
        print(f"- {country}: {count}건")
    return JSONResponse(content=counter)


DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1382606716755120172/mL1YfvyWD54kOjmtCEn4WxCL9yDu6NdAdXzhEpZw7lTP3QQB2rQ01lMEq2tRLWKJq4zC"  
 # 실제 웹훅 주소로 변경

@router.post("/api/send-pdf-discord")
async def send_pdf_discord(file: UploadFile = File(...)):
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field('file', await file.read(), filename=file.filename, content_type='application/pdf')
        async with session.post(DISCORD_WEBHOOK, data=form) as resp:
            if resp.status == 204:
                return JSONResponse(content={"status": "ok"})
            return JSONResponse(content={"status": "error", "detail": await resp.text()})

