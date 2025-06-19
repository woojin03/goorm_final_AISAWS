from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import collector  # ✅ 이거 가능하려면 구조 맞춰야 함
from app.routers import analyze
from app.routers import dashboard
from app.routers import report
from app.routers import log

app = FastAPI()

app.include_router(collector.router)
app.include_router(analyze.router)
app.include_router(dashboard.router)  # 👉 chart API용
app.include_router(report.router)
app.include_router(log.router)

# 정적 파일 mount
app.mount("/static", StaticFiles(directory="static"), name="static")


# ✅ 템플릿 디렉토리 경로 수정
templates = Jinja2Templates(directory="templates")

'''
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "page": "dashboard"})
'''

@app.get("/log-input", response_class=HTMLResponse)
async def log_input(request: Request):
    return templates.TemplateResponse("log_input.html", {"request": request, "page": "log"})

'''@app.get("/chat", response_class=HTMLResponse)
async def chat(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request, "page": "chat"})'''

@app.get("/chat", response_class=HTMLResponse)
async def chat(request: Request, selected_report: str = None):
    dummy_chats = {
        "2025-05-15~2025-05-17": [
            {"role": "assistant", "text": "2025년 5월 15일부터 17일까지의 로그 분석입니다."},
            {"role": "user", "text": "ip 권한 설정에 대해서 종합적으로 분석해줘"},
            {"role": "assistant", "text": "설정된 권한은 IAM Role을 통해..."}
        ],
        "2025-05-18~2025-05-19": [],
        "2025-05-20~2025-05-21": [],
    }

    report_list = list(dummy_chats.keys())
    chat_history = dummy_chats.get(selected_report, []) if selected_report else []

    return templates.TemplateResponse("chat.html", {
        "request": request,
        "page": "chat",
        "report_list": report_list,
        "selected_report": selected_report,
        "chat_history": chat_history
    })



@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request, "page": "settings"})
