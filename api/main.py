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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import indicators, kline, stocks, watchlist

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
    allow_methods=["GET"],
    allow_headers=["*"],
)

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
    """服务健康检查，返回 ok 和当前时间戳。"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

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
