# app/routers/collector.py

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.helpers.collector_runner import run_collectors_stream  # ✅ subprocess 실행용 runner
import asyncio
import json

router = APIRouter()

class CollectRequest(BaseModel):
    start: str
    end: str
    prompt: str

@router.post("/collect")
async def collect_logs(request: Request):
    body = await request.json()
    start = body.get("start")
    end = body.get("end")
    prompt = body.get("prompt")

    def stream_generator():
        try:
            yield f"🔍 수집 시작: {start} ~ {end}\n"
            for line in run_collectors_stream(start, end):  # ✅ 동기 generator
                yield line
            yield "\n✅ 로그 수집 완료\n"
        except Exception as e:
            yield f"\n[ERROR] 수집 실패: {str(e)}\n"

    return StreamingResponse(stream_generator(), media_type="text/plain")

