#!/usr/bin/env bash
# deploy/start.sh — 目标机服务启动脚本（macOS）
# 启动 uvicorn Web 服务（后台 nohup，PID 写入 data/web.pid）
#
# 环境变量：
#   DEPLOY_DIR   — 项目部署目录，默认脚本所在目录的上级
#   WEB_PORT     — Web 服务端口，默认 8000

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
WEB_PORT="${WEB_PORT:-8000}"

VENV_DIR="${DEPLOY_DIR}/env_quant"
UVICORN="${VENV_DIR}/bin/uvicorn"
PID_FILE="${DEPLOY_DIR}/data/web.pid"
LOG_FILE="${DEPLOY_DIR}/logs/web.log"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI 量化辅助决策系统 — 启动 Web 服务"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── 检查部署目录 ────────────────────────────────────────────
if [[ ! -d "$DEPLOY_DIR" ]]; then
    error "部署目录不存在：${DEPLOY_DIR}"
    error "请先运行 deploy.sh 完成部署"
    exit 1
fi

# ─── 检查虚拟环境 ────────────────────────────────────────────
if [[ ! -f "$UVICORN" ]]; then
    error "uvicorn 未找到：${UVICORN}"
    error "请先运行 deploy.sh 安装依赖"
    exit 1
fi

# ─── 检查是否已在运行 ────────────────────────────────────────
if [[ -f "$PID_FILE" ]]; then
    EXISTING_PID=$(cat "$PID_FILE")
    if kill -0 "$EXISTING_PID" 2>/dev/null; then
        warn "Web 服务已在运行（PID: ${EXISTING_PID}）"
        warn "如需重启，请先运行 stop.sh"
        exit 0
    else
        info "发现过期 PID 文件（进程 ${EXISTING_PID} 已不存在），清理..."
        rm -f "$PID_FILE"
    fi
fi

# ─── 创建运行时目录 ──────────────────────────────────────────
mkdir -p "${DEPLOY_DIR}/data"
mkdir -p "${DEPLOY_DIR}/logs"

# ─── DB 表结构迁移 + watchlist 股票名称同步 ──────────────────
info "运行数据库迁移（表结构升级 + 股票名称同步）..."
cd "$DEPLOY_DIR"
if "${VENV_DIR}/bin/python" main.py migrate; then
    info "数据库迁移完成"
else
    warn "数据库迁移失败，请检查日志，服务仍将尝试启动"
fi

# ─── 加载 .env 配置 ──────────────────────────────────────────
ENV_FILE="${DEPLOY_DIR}/.env"
if [[ -f "$ENV_FILE" ]]; then
    # 直接 source .env：bash 原生处理 # 注释和空行，比 grep 过滤更稳定
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    info "已加载配置：${ENV_FILE}"
fi

# 端口/主机优先级：环境变量 > .env > 默认值
WEB_PORT="${WEB_PORT:-8000}"
WEB_HOST="${WEB_HOST:-127.0.0.1}"

# ─── 启动 uvicorn ────────────────────────────────────────────
info "启动 uvicorn（host=${WEB_HOST}，port=${WEB_PORT}，生产模式）..."
info "日志输出：${LOG_FILE}"

cd "$DEPLOY_DIR"

nohup "${UVICORN}" api.main:app \
    --host "${WEB_HOST:-127.0.0.1}" \
    --port "${WEB_PORT}" \
    --workers 1 \
    --log-level info \
    >> "${LOG_FILE}" 2>&1 &

WEB_PID=$!
echo "$WEB_PID" > "$PID_FILE"

# ─── 等待服务就绪（最多 10 秒） ──────────────────────────────
info "等待服务就绪（最多 10 秒）..."
READY=false
for i in $(seq 1 10); do
    sleep 1
    # 检查进程是否还活着
    if ! kill -0 "$WEB_PID" 2>/dev/null; then
        error "服务启动失败，进程已退出"
        error "查看日志：tail -50 ${LOG_FILE}"
        rm -f "$PID_FILE"
        exit 1
    fi
    # 尝试连接
    if command -v curl &>/dev/null; then
        if curl -sf "http://localhost:${WEB_PORT}/api/health" &>/dev/null || \
           curl -sf "http://localhost:${WEB_PORT}/" &>/dev/null; then
            READY=true
            break
        fi
    else
        # 无 curl，用 nc 检查端口
        if command -v nc &>/dev/null; then
            if nc -z localhost "${WEB_PORT}" 2>/dev/null; then
                READY=true
                break
            fi
        else
            # 无法检查，等待 3 秒后假定成功
            if [[ $i -ge 3 ]]; then
                READY=true
                break
            fi
        fi
    fi
    echo -n "."
done
echo ""

if $READY; then
    success "Web 服务已启动！"
    echo ""
    echo "  PID：${WEB_PID}"
    echo "  端口：${WEB_PORT}"
    echo "  日志：${LOG_FILE}"
    echo "  PID 文件：${PID_FILE}"
    echo ""
    echo "  访问地址：http://localhost:${WEB_PORT}"
    echo ""
    echo "  停止服务：bash $(dirname "${BASH_SOURCE[0]}")/stop.sh"
else
    warn "服务可能仍在启动中（10 秒内未响应 HTTP）"
    warn "请稍等片刻后手动检查："
    warn "  curl http://localhost:${WEB_PORT}/api/health"
    warn "  tail -f ${LOG_FILE}"
    echo ""
    echo "  PID：${WEB_PID}（服务进程仍在运行）"
fi

# ─── 安装数据同步定时任务（仅 macOS） ────────────────────────
echo ""
echo "── 数据同步定时任务 ──────────────────────────────────────"
SYNC_LABEL="com.quant.sync"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
SYNC_PLIST_SRC="${DEPLOY_DIR}/deploy/com.quant.sync.plist"
SYNC_PLIST_DST="${LAUNCH_AGENTS_DIR}/${SYNC_LABEL}.plist"

if [[ "$(uname)" != "Darwin" ]]; then
    warn "非 macOS 系统，跳过 launchd 定时任务安装"
    warn "Linux 用户请参考 deploy/README.md 使用 systemd timer"
elif [[ ! -f "$SYNC_PLIST_SRC" ]]; then
    warn "未找到 ${SYNC_PLIST_SRC}，跳过定时任务安装"
else
    mkdir -p "${LAUNCH_AGENTS_DIR}"

    # 用实际路径替换占位符后写入 LaunchAgents
    sed "s|/Users/YOUR_USER/code_quant|${DEPLOY_DIR}|g" \
        "${SYNC_PLIST_SRC}" > "${SYNC_PLIST_DST}"

    # 若已加载则先卸载（升级场景），忽略报错
    launchctl unload "${SYNC_PLIST_DST}" 2>/dev/null || true

    if launchctl load "${SYNC_PLIST_DST}" 2>/dev/null; then
        success "数据同步定时任务已安装并加载（${SYNC_LABEL}）"
        info  "  每个交易日 16:30 自动触发数据同步"
        info  "  手动立即触发：launchctl start ${SYNC_LABEL}"
        info  "  查看状态：    launchctl list | grep quant"
        info  "  同步日志：    ${DEPLOY_DIR}/logs/sync.log"
    else
        warn "launchctl load 失败，请手动执行："
        warn "  launchctl load ${SYNC_PLIST_DST}"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
