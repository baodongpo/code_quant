#!/usr/bin/env bash
# pack.sh — 开发机打包脚本
# 用法：./pack.sh [版本号]
# 示例：./pack.sh 0.3.0
# 输出：dist/code_quant-v<版本>-<日期>.tar.gz

set -euo pipefail

# ─── 颜色输出 ────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ─── 版本号 ──────────────────────────────────────────────────
VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    warn "未指定版本号，将使用 'dev' 作为版本标识"
    VERSION="dev"
fi

DATE=$(date +%Y%m%d)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="code_quant"
ARCHIVE_NAME="${PROJECT_NAME}-v${VERSION}-${DATE}.tar.gz"
DIST_DIR="${SCRIPT_DIR}/dist"
ARCHIVE_PATH="${DIST_DIR}/${ARCHIVE_NAME}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI 量化辅助决策系统 — 打包脚本"
echo "  版本: v${VERSION}   日期: ${DATE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$SCRIPT_DIR"

# ─── Step 1: 检查 Node.js / npm ──────────────────────────────
info "检查 Node.js / npm 可用性..."
if ! command -v node &>/dev/null; then
    error "未找到 node 命令，请先安装 Node.js（https://nodejs.org）"
    exit 1
fi
if ! command -v npm &>/dev/null; then
    error "未找到 npm 命令，请先安装 npm"
    exit 1
fi
NODE_VERSION=$(node --version)
NPM_VERSION=$(npm --version)
success "Node.js ${NODE_VERSION}，npm ${NPM_VERSION}"

# ─── Step 2: 构建前端 ────────────────────────────────────────
info "构建前端（web/dist/）..."
if [[ ! -d "${SCRIPT_DIR}/web" ]]; then
    error "web/ 目录不存在，请确认在项目根目录执行此脚本"
    exit 1
fi

cd "${SCRIPT_DIR}/web"
info "  npm install..."
npm install --silent
info "  npm run build..."
npm run build
cd "${SCRIPT_DIR}"

if [[ ! -d "${SCRIPT_DIR}/web/dist" ]]; then
    error "前端构建失败：web/dist/ 目录不存在"
    exit 1
fi
success "前端构建完成：web/dist/"

# ─── Step 3: 创建 dist/ 目录 ─────────────────────────────────
info "创建 dist/ 输出目录..."
mkdir -p "${DIST_DIR}"
success "dist/ 目录就绪"

# ─── Step 4: 打包（排除无关内容） ────────────────────────────
info "打包 → ${ARCHIVE_NAME}..."
info "  排除：env_quant/ web/node_modules/ data/ logs/ .env watchlist.json .git/ __pycache__/ exports/"

tar -czf "${ARCHIVE_PATH}" \
    --exclude="./${PROJECT_NAME}/env_quant" \
    --exclude="./env_quant" \
    --exclude="./${PROJECT_NAME}/web/node_modules" \
    --exclude="./web/node_modules" \
    --exclude="./${PROJECT_NAME}/data" \
    --exclude="./data" \
    --exclude="./${PROJECT_NAME}/logs" \
    --exclude="./logs" \
    --exclude="./${PROJECT_NAME}/.env" \
    --exclude="./.env" \
    --exclude="./${PROJECT_NAME}/watchlist.json" \
    --exclude="./watchlist.json" \
    --exclude="./${PROJECT_NAME}/.git" \
    --exclude="./.git" \
    --exclude="./${PROJECT_NAME}/__pycache__" \
    --exclude="./__pycache__" \
    --exclude="*/__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    --exclude="./${PROJECT_NAME}/exports" \
    --exclude="./exports" \
    --exclude="./${PROJECT_NAME}/dist" \
    -C "${SCRIPT_DIR}/.." \
    "${PROJECT_NAME}"

ARCHIVE_SIZE=$(du -sh "${ARCHIVE_PATH}" | cut -f1)
success "打包完成：${ARCHIVE_PATH}（${ARCHIVE_SIZE}）"

# ─── Step 5: 验证关键内容 ─────────────────────────────────────
info "验证打包内容..."

# 确认排除项不在包内
EXCLUDED_CHECK=0
for EXCLUDED in "env_quant/" "data/" ".env" "watchlist.json"; do
    if tar -tzf "${ARCHIVE_PATH}" 2>/dev/null | grep -qE "(^|/)${EXCLUDED%/}(/|$)"; then
        warn "  意外包含了：${EXCLUDED}"
        EXCLUDED_CHECK=1
    fi
done
if [[ $EXCLUDED_CHECK -eq 0 ]]; then
    success "  排除项验证通过（env_quant/ data/ .env watchlist.json 均不在包内）"
fi

# 确认前端构建产物在包内
if tar -tzf "${ARCHIVE_PATH}" 2>/dev/null | grep -q "web/dist/"; then
    success "  前端构建产物 web/dist/ 已包含"
else
    warn "  未找到 web/dist/，前端构建产物可能未包含"
fi

# ─── Step 6: 打印传输提示 ────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}  打包成功！${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  制品路径：${ARCHIVE_PATH}"
echo ""
echo "  ── 传输到目标机 ──────────────────────────────────"
echo "  scp 方式："
echo "    scp ${ARCHIVE_PATH} user@server:~/"
echo ""
echo "  rsync 方式（断点续传）："
echo "    rsync -avP ${ARCHIVE_PATH} user@server:~/"
echo ""
echo "  ── 在目标机部署 ──────────────────────────────────"
echo "  首次部署："
echo "    bash deploy.sh ${ARCHIVE_NAME}"
echo ""
echo "  升级（自动重启服务）："
echo "    bash deploy.sh ${ARCHIVE_NAME} --restart"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
