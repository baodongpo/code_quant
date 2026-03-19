#!/usr/bin/env bash
# deploy/stop.sh — 目标机服务停止脚本（macOS）
# 读取 data/web.pid 发送 SIGTERM，等待进程退出，清理 PID 文件
#
# 用法：
#   bash stop.sh           — 只停 Web 服务（升级/维护用，sync 定时任务保留）
#   bash stop.sh --full    — 停 Web 服务 + 卸载 sync 定时任务（完全关闭）
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

# ─── 参数解析 ────────────────────────────────────────────────
DO_FULL=false
for arg in "$@"; do
    case "$arg" in
        --full) DO_FULL=true ;;
    esac
done

# ─── 路径配置 ────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="${DEPLOY_DIR:-$(dirname "$SCRIPT_DIR")}"
PID_FILE="${DEPLOY_DIR}/data/web.pid"

# 最大等待秒数
STOP_TIMEOUT="${STOP_TIMEOUT:-30}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if $DO_FULL; then
    echo "  AI 量化辅助决策系统 — 完全停止（Web + 同步定时任务）"
else
    echo "  AI 量化辅助决策系统 — 停止 Web 服务"
fi
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

    # --full 模式下仍需卸载 sync 定时任务
    if $DO_FULL; then
        echo ""
        echo "── 卸载数据同步定时任务 ──────────────────────────────────"
        SYNC_LABEL="com.quant.sync"
        SYNC_PLIST_DST="${HOME}/Library/LaunchAgents/${SYNC_LABEL}.plist"
        if [[ "$(uname)" != "Darwin" ]]; then
            warn "非 macOS 系统，跳过 launchd 卸载"
        elif [[ ! -f "$SYNC_PLIST_DST" ]]; then
            info "未找到 ${SYNC_PLIST_DST}，定时任务可能未安装，跳过"
        else
            launchctl unload "${SYNC_PLIST_DST}" 2>/dev/null || true
            rm -f "${SYNC_PLIST_DST}"
            success "数据同步定时任务已卸载（${SYNC_LABEL}）"
        fi
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
    # --full 模式下仍需卸载 sync 定时任务
    if $DO_FULL; then
        echo ""
        echo "── 卸载数据同步定时任务 ──────────────────────────────────"
        SYNC_LABEL="com.quant.sync"
        SYNC_PLIST_DST="${HOME}/Library/LaunchAgents/${SYNC_LABEL}.plist"
        if [[ "$(uname)" != "Darwin" ]]; then
            warn "非 macOS 系统，跳过 launchd 卸载"
        elif [[ ! -f "$SYNC_PLIST_DST" ]]; then
            info "未找到 ${SYNC_PLIST_DST}，定时任务可能未安装，跳过"
        else
            launchctl unload "${SYNC_PLIST_DST}" 2>/dev/null || true
            rm -f "${SYNC_PLIST_DST}"
            success "数据同步定时任务已卸载（${SYNC_LABEL}）"
        fi
    fi
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

# ─── --full 模式：卸载 sync 定时任务 ─────────────────────────
if $DO_FULL; then
    echo ""
    echo "── 卸载数据同步定时任务 ──────────────────────────────────"
    SYNC_LABEL="com.quant.sync"
    SYNC_PLIST_DST="${HOME}/Library/LaunchAgents/${SYNC_LABEL}.plist"

    if [[ "$(uname)" != "Darwin" ]]; then
        warn "非 macOS 系统，跳过 launchd 卸载"
        warn "Linux 用户请手动执行：systemctl disable --now quant-sync*.timer"
    elif [[ ! -f "$SYNC_PLIST_DST" ]]; then
        info "未找到 ${SYNC_PLIST_DST}，定时任务可能未安装，跳过"
    else
        launchctl unload "${SYNC_PLIST_DST}" 2>/dev/null || true
        rm -f "${SYNC_PLIST_DST}"
        success "数据同步定时任务已卸载（${SYNC_LABEL}）"
        info  "  如需重新启用，执行：bash ${SCRIPT_DIR}/start.sh"
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
