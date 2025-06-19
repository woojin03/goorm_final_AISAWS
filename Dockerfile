FROM python:3.12.7-slim

WORKDIR /app

# 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# app 폴더 전체 복사 (main.py 포함)
COPY app/ ./app/

# static 폴더 복사
COPY static/ ./static/

# templates 폴더 복사 (템플릿이 여기에 있으니까)
COPY templates/ ./templates/

# 앱 실행 (main.py가 app 폴더 안에 있으므로 경로도 맞춰줘야 함)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
