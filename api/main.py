"""
api/main.py — FastAPI 应用入口

启动方式：
  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload   # 开发
  uvicorn api.main:app --host 0.0.0.0 --port $WEB_PORT        # 生产

生产模式下自动 serve 前端构建产物（web/dist/）。
严格只读：不写入数据库，不包含任何交易逻辑。
"""

import os
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.routes import indicators, kline, stocks, watchlist
from config.settings import WEB_ACCESS_TOKEN, APP_VERSION

# ---------------------------------------------------------------------------
# 应用初始化
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI 量化辅助决策系统 - Web API",
    description=(
        "提供 K线数据及技术指标 REST API，严格只读。"
        "不包含任何交易、下单逻辑。"
    ),
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS（开发模式允许 Vite dev server）
# ---------------------------------------------------------------------------

_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Token 鉴权中间件（FEAT-04：局域网访问 + Token 鉴权）
# ---------------------------------------------------------------------------

_403_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>403 Forbidden</title></head>
<body style="font-family:sans-serif;text-align:center;padding:80px;color:#555">
<h1>403 Forbidden</h1>
<p>访问被拒绝。请携带有效的 <code>?token=</code> 参数后重试。</p>
</body></html>"""


_COOKIE_NAME = "wat"  # web access token


class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. OPTIONS 预检直接放行（必须最优先，否则浏览器跨域失败）
        if request.method == "OPTIONS":
            return await call_next(request)
        # 2. 本机回环豁免
        client_ip = request.client.host if request.client else ""
        if client_ip in ("127.0.0.1", "::1"):
            return await call_next(request)
        # 3. token 未配置时不启用鉴权
        if not WEB_ACCESS_TOKEN:
            return await call_next(request)
        # 4. 校验 token（Header > query param > Cookie）
        token = (
            request.headers.get("X-Access-Token")
            or request.query_params.get("token", "")
            or request.cookies.get(_COOKIE_NAME, "")
        )
        if token == WEB_ACCESS_TOKEN:
            response = await call_next(request)
            # 首次通过 query/header 鉴权时写 Cookie，使浏览器后续静态资源请求无需再带 token
            if _COOKIE_NAME not in request.cookies:
                response.set_cookie(
                    key=_COOKIE_NAME,
                    value=WEB_ACCESS_TOKEN,
                    httponly=True,
                    samesite="lax",
                    max_age=86400 * 7,  # 7天
                )
            return response
        # 5. 鉴权失败
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return HTMLResponse(_403_HTML, status_code=403)
        return JSONResponse({"detail": "Unauthorized"}, status_code=403)


app.add_middleware(TokenAuthMiddleware)

# ---------------------------------------------------------------------------
# 路由挂载（均在 /api 前缀下）
# ---------------------------------------------------------------------------

app.include_router(stocks.router,     prefix="/api")
app.include_router(kline.router,      prefix="/api")
app.include_router(watchlist.router,  prefix="/api")
app.include_router(indicators.router, prefix="/api")

# ---------------------------------------------------------------------------
# 健康检查（无需 DB，纯内存，供 start.sh / 监控使用）
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["system"])
def health():
    """服务健康检查，返回 ok、当前时间戳和版本号。"""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
    }

# ---------------------------------------------------------------------------
# 生产模式：serve 前端构建产物
# ---------------------------------------------------------------------------

_web_mode = os.getenv("WEB_MODE", "development").lower()
_web_dist  = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dist")

if _web_mode == "production" and os.path.isdir(_web_dist):
    from fastapi.staticfiles import StaticFiles

    # SPA fallback: 先尝试静态文件，404 时返回 index.html
    # mount 放在所有 API 路由之后，确保 /api/* 优先匹配
    app.mount("/", StaticFiles(directory=_web_dist, html=True), name="static")
