# app/routers/log.py

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from app.helpers.db_utils import get_logs_by_report_id
import os

router = APIRouter()

@router.get("/get-log")
def get_log(report_id: str):
    try:
        MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        logs = get_logs_by_report_id(MONGODB_URI, report_id)
        if not logs:
            return JSONResponse(content={"logs": ""})
        
        # 너무 많을 경우 제한 (최대 10,000자)
        #text = "\n".join([str(log) for log in logs])[:50000]
        text = "\n".join([str(log) for log in logs])
        return JSONResponse(content={"logs": text})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
