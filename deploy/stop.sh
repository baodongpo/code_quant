#!/usr/bin/env bash
# deploy/stop.sh — 目标机服务停止脚本（macOS）
# 读取 data/web.pid 发送 SIGTERM，等待进程退出，清理 PID 文件
#
# 环境变量：
#   DEPLOY_DIR   — 项目部署目录，默认脚本所在目录的上级

set -euo pipefail

# ─── 颜色输出 ────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ─── 路径配置 ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="${DEPLOY_DIR:-$(dirname "$SCRIPT_DIR")}"
PID_FILE="${DEPLOY_DIR}/data/web.pid"

# 最大等待秒数
STOP_TIMEOUT="${STOP_TIMEOUT:-30}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI 量化辅助决策系统 — 停止 Web 服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── 读取 PID ────────────────────────────────────────────────
if [[ ! -f "$PID_FILE" ]]; then
    warn "PID 文件不存在：${PID_FILE}"
    warn "服务可能未在运行，或 PID 文件已被删除"
    echo ""

    # 尝试通过进程名找到 uvicorn 进程（补救措施）
    UVICORN_PIDS=$(pgrep -f "uvicorn api.main:app" 2>/dev/null || true)
    if [[ -n "$UVICORN_PIDS" ]]; then
        warn "通过进程名找到 uvicorn 进程：${UVICORN_PIDS}"
        warn "尝试终止..."
        echo "$UVICORN_PIDS" | xargs kill -TERM 2>/dev/null || true
        sleep 2
        # 确认进程已退出
        REMAINING=$(pgrep -f "uvicorn api.main:app" 2>/dev/null || true)
        if [[ -z "$REMAINING" ]]; then
            success "uvicorn 进程已终止"
        else
            warn "部分进程仍在运行，尝试 SIGKILL..."
            echo "$REMAINING" | xargs kill -KILL 2>/dev/null || true
        fi
    else
        info "未发现运行中的 uvicorn 进程，无需操作"
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    exit 0
fi

WEB_PID=$(cat "$PID_FILE")
info "读取 PID 文件：${PID_FILE} → PID ${WEB_PID}"

# ─── 检查进程是否存在 ────────────────────────────────────────
if ! kill -0 "$WEB_PID" 2>/dev/null; then
    warn "进程 ${WEB_PID} 已不存在（可能已崩溃或被手动终止）"
    info "清理过期 PID 文件..."
    rm -f "$PID_FILE"
    success "PID 文件已清理"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    exit 0
fi

# ─── 发送 SIGTERM ────────────────────────────────────────────
info "发送 SIGTERM 到进程 ${WEB_PID}..."
kill -TERM "$WEB_PID"

# ─── 等待进程退出 ────────────────────────────────────────────
info "等待进程退出（最多 ${STOP_TIMEOUT} 秒）..."
ELAPSED=0
while kill -0 "$WEB_PID" 2>/dev/null; do
    sleep 1
    ELAPSED=$((ELAPSED + 1))
    if [[ $ELAPSED -ge $STOP_TIMEOUT ]]; then
        warn "进程 ${WEB_PID} 在 ${STOP_TIMEOUT} 秒内未退出，发送 SIGKILL..."
        kill -KILL "$WEB_PID" 2>/dev/null || true
        sleep 1
        break
    fi
    echo -n "."
done
echo ""

# ─── 清理 PID 文件 ───────────────────────────────────────────
rm -f "$PID_FILE"

# ─── 确认进程已终止 ──────────────────────────────────────────
if kill -0 "$WEB_PID" 2>/dev/null; then
    error "进程 ${WEB_PID} 仍在运行，请手动处理：kill -9 ${WEB_PID}"
    exit 1
fi

success "Web 服务已停止（PID: ${WEB_PID}）"
echo ""
echo "  PID 文件已清理：${PID_FILE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
