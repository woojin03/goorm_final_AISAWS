# app/routers/analyze.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.helpers.export_log import export_logs
from app.helpers.llama_index_runner import run_llama_index_analysis
from pathlib import Path
import json
import traceback

router = APIRouter()

SORT_FIELDS = {
    "cloudtrail": "EventTime",
    "vpcflow": "start",
    "s3accesslog": "time"
}

class AnalyzeRequest(BaseModel):
    start: str
    end: str
    prompt: str

@router.post("/analyze")
async def analyze_logs(req: AnalyzeRequest):
    try:
        report_id = f"report_{req.start.replace('-', '')}_{req.end.replace('-', '')}"
        print(f"[INFO] ▶️ 분석 시작: {report_id}")

        # ✅ 1. 로그 수집 및 정렬
        logs = export_logs(req.start, req.end)
        flat_logs = []

        for log_type, entries in logs.items():
            time_key = SORT_FIELDS.get(log_type)
            for entry in entries:
                timestamp = entry.get(time_key)
                if timestamp:
                    flat_logs.append({
                        "log_type": log_type,
                        "timestamp": timestamp,
                        "log": entry
                    })

        sorted_logs = sorted(flat_logs, key=lambda x: x["timestamp"])
        log_entries = [item["log"] for item in sorted_logs]
        print(f"[DEBUG] ✅ 총 수집된 로그 수: {len(log_entries)}")

        if not sorted_logs:
            return {"status": "error", "message": "❌ 수집된 로그가 없습니다."}

        # ✅ 2. 슬라이싱 분석 (중간 저장 포함)
        chunk_size = 400
        summaries = []
        temp_path = Path("temp_chunk_summaries.jsonl")

        if temp_path.exists():
            temp_path.unlink()  # 이전 결과 삭제
            print(f"[INFO] 🧹 이전 중간 저장 파일 삭제: {temp_path}")

        print(f"[INFO] 🔁 슬라이싱 시작: chunk_size={chunk_size}, 총 {len(log_entries) // chunk_size + 1}회")

        for i in range(0, len(log_entries), chunk_size):
            chunk = log_entries[i:i + chunk_size]
            print(f"[INFO] 🔍 {i + 1} ~ {i + len(chunk)} 로그 분석 중...")

            try:
                chunk_summary = run_llama_index_analysis(chunk, req.prompt)
                summary_text = chunk_summary.strip()
                print(f"[DEBUG] ✅ 요약 {i // chunk_size + 1} 길이: {len(summary_text)}자")
            except Exception as e:
                summary_text = f"[요약 {i // chunk_size + 1}] 분석 실패: {str(e)}"
                print(f"[ERROR] ❌ 요약 {i // chunk_size + 1} 실패: {e}")

            summaries.append(f"[요약 {i // chunk_size + 1}]\n{summary_text}")

            with temp_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "index": i,
                    "summary": summary_text
                }, ensure_ascii=False) + "\n")

        # ✅ 3. 최종 분석 생략: 중간 요약만 반환
        final_result = "\n\n".join(summaries)

        # ✅ 4. 리포트 저장
        report = {
            "report_id": report_id,
            "start": req.start,
            "end": req.end,
            "prompt": req.prompt,
            "summary": final_result,  # 통합 요약이 아니라 슬라이스 요약 전체
            "messages": [
                {"role": "user", "text": req.prompt},
                *[{"role": "assistant", "text": s} for s in summaries]
            ]
        }


        try:
            base_dir = Path(__file__).resolve().parent.parent.parent
            save_path = base_dir / f"reports/{report_id}.json"
            save_path.parent.mkdir(parents=True, exist_ok=True)

            with save_path.open("w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"[INFO] 💾 리포트 저장 완료: {save_path}")

        except Exception as save_err:
            print(f"[ERROR] ❗ 리포트 저장 실패: {save_err}")

        return {
            "status": "success",
            "analysis": final_result,
            "report_id": report_id
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"분석 중 오류 발생: {str(e)}")
