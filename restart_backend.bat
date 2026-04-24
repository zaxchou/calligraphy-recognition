@echo off
cd /d z:\BaiduSync\BaiduSyncdisk\calligraphy-recognition\backend
start /B python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
