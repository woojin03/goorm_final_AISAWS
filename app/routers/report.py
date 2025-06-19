from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
from typing import Optional

router = APIRouter()

class UpdateReportRequest(BaseModel):
    report_id: str
    start: Optional[str] = ""
    end: Optional[str] = ""
    text: str
    role: str  # "user" 또는 "assistant"

@router.post("/create-report")
async def create_report(req: UpdateReportRequest):
    base_dir = Path(__file__).resolve().parent.parent.parent
    path = base_dir / f"reports/{req.report_id}.json"

    if path.exists():
        return {"status": "already_exists"}

    new_report = {
        "report_id": req.report_id,
        "start": req.start,
        "end": req.end,
        "prompt": req.text,
        "summary": "",
        "messages": []
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(new_report, f, ensure_ascii=False, indent=2)

    return {"status": "created"}

@router.post("/update-report")
async def update_report(req: UpdateReportRequest):
    base_dir = Path(__file__).resolve().parent.parent.parent
    path = base_dir / f"reports/{req.report_id}.json"

    if not path.exists():
        raise HTTPException(status_code=404, detail="리포트 파일이 존재하지 않습니다.")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    data.setdefault("messages", []).append({
        "role": req.role,
        "text": req.text
    })

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {"status": "ok"}

@router.get("/report/{report_id}")
async def get_report(report_id: str):
    try:
        base_dir = Path(__file__).resolve().parent.parent.parent
        path = base_dir / f"reports/{report_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="리포트가 존재하지 않습니다.")
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"불러오기 실패: {str(e)}")