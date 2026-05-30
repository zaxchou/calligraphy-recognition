---
name: fix-cors-backend
overview: 修 CORS 跨域问题，使前端 localhost:3000 能访问后端 API
todos:
  - id: fix-cors-env
    content: 修改 backend/.env，取消 CORS_ALLOW_ORIGINS 注释并设置为 http://localhost:3000
    status: completed
---

修复前端 `http://localhost:3000` 访问后端 API `http://localhost:8001` 时的 CORS 跨域问题。

## 问题根因

- `.env` 中 `CORS_ALLOW_ORIGINS` 被注释掉
- FastAPI 读取不到来源配置，导致 CORS 中间件拒绝跨域请求
- 浏览器报错：`No 'Access-Control-Allow-Origin' header is present`

## 修复方案

取消 `.env` 中 `CORS_ALLOW_ORIGINS` 的注释，设置为前端地址 `http://localhost:3000`，然后重启 uvicorn 使配置生效。

## 影响范围

- 仅修改 `backend/.env` 一行
- 重启后端服务进程
- 无副作用，不影响其他 API 路由

## 技术方案

修改 `backend/.env` 第 65 行：

- 旧值：`# CORS_ALLOW_ORIGINS=*`
- 新值：`CORS_ALLOW_ORIGINS=http://localhost:3000`

FastAPI 的 `CORSMiddleware` 会读取 `settings.CORS_ALLOW_ORIGINS`，当前为 `None`（因被注释），兜底逻辑会设 `origins = ["*"]`，但此时 `allow_credentials=True`，浏览器直接拒绝跨域。设置为明确的前端地址后 `allow_credentials=False`，请求正常放行。

# Agent Extensions

无。