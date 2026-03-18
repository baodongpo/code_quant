#!/usr/bin/env bash
# deploy/deploy.sh — 目标机部署/升级脚本
# 用法：./deploy.sh <制品.tar.gz> [--restart]
# 示例：./deploy.sh code_quant-v0.3.0-20260318.tar.gz --restart
#
# 环境变量：
#   DEPLOY_DIR   — 部署目标目录，默认 ~/code_quant
#   PYTHON_BIN   — Python 可执行文件路径，默认自动探测 python3.10/python3

set -euo pipefail

# ─── 颜色输出 ────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
step()    { echo -e "\n${BOLD}── $* ${NC}"; }

# ─── 参数解析 ────────────────────────────────────────────────
ARCHIVE="${1:-}"
DO_RESTART=false

for arg in "$@"; do
    case "$arg" in
        --restart) DO_RESTART=true ;;
    esac
done

if [[ -z "$ARCHIVE" ]]; then
    error "用法：$0 <制品.tar.gz> [--restart]"
    error "示例：$0 code_quant-v0.3.0-20260318.tar.gz --restart"
    exit 1
fi

if [[ ! -f "$ARCHIVE" ]]; then
    error "制品文件不存在：$ARCHIVE"
    exit 1
fi

# ─── 配置 ────────────────────────────────────────────────────
DEPLOY_DIR="${DEPLOY_DIR:-${HOME}/code_quant}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  AI 量化辅助决策系统 — 部署/升级脚本"
echo "  制品：$(basename "$ARCHIVE")"
echo "  目标：${DEPLOY_DIR}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── 探测 Python 3.10+ ──────────────────────────────────────
step "检查 Python 3.10+"

find_python310() {
    for cmd in "${PYTHON_BIN:-}" python3.10 python3.11 python3.12 python3; do
        [[ -z "$cmd" ]] && continue
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
            local major minor
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [[ "$major" -eq 3 && "$minor" -ge 10 ]]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

if PYTHON_BIN=$(find_python310); then
    PY_VER=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
    success "找到 Python ${PY_VER}：$(command -v "$PYTHON_BIN")"
else
    error "未找到 Python 3.10+。"
    error "macOS 安装方式（推荐 Homebrew）："
    error "  brew install python@3.10"
    error "或访问 https://www.python.org/downloads/"
    exit 1
fi

# ─── 判断首次部署 vs 升级 ────────────────────────────────────
IS_UPGRADE=false
if [[ -d "${DEPLOY_DIR}/env_quant" ]]; then
    IS_UPGRADE=true
    echo ""
    info "检测到已有部署（env_quant/ 存在），执行 ${YELLOW}升级流程${NC}"
else
    echo ""
    info "未检测到已有部署，执行 ${GREEN}首次部署流程${NC}"
fi

# ─── 升级：停止服务 ──────────────────────────────────────────
if $IS_UPGRADE && $DO_RESTART; then
    step "停止现有服务"
    STOP_SCRIPT="${DEPLOY_DIR}/deploy/stop.sh"
    if [[ -f "$STOP_SCRIPT" ]]; then
        bash "$STOP_SCRIPT" || warn "停止服务时发生错误（可能服务未在运行），继续..."
    else
        warn "未找到 stop.sh，跳过停止步骤"
    fi
fi

# ─── 解压制品 ────────────────────────────────────────────────
step "解压制品"

ARCHIVE_ABS="$(cd "$(dirname "$ARCHIVE")" && pwd)/$(basename "$ARCHIVE")"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

info "解压到临时目录：${TMP_DIR}..."
tar -xzf "${ARCHIVE_ABS}" -C "${TMP_DIR}"

# 找到解压后的项目目录（tar 包内顶层目录为 code_quant）
EXTRACTED_DIR=""
for d in "${TMP_DIR}"/*/; do
    EXTRACTED_DIR="${d%/}"
    break
done

if [[ -z "$EXTRACTED_DIR" || ! -d "$EXTRACTED_DIR" ]]; then
    error "解压失败：无法找到顶层目录"
    exit 1
fi
success "解压成功：$(basename "$EXTRACTED_DIR")"

# ─── 首次部署：创建目录结构 ──────────────────────────────────
if ! $IS_UPGRADE; then
    step "首次部署：初始化目录"
    mkdir -p "${DEPLOY_DIR}"
    info "复制项目文件到 ${DEPLOY_DIR}..."
    cp -r "${EXTRACTED_DIR}/." "${DEPLOY_DIR}/"
    success "项目文件已复制"
else
    # ─── 升级：rsync 覆盖代码（跳过用户配置和数据） ─────────
    step "升级：同步代码文件（保留用户数据）"
    info "rsync 覆盖代码（跳过 data/ .env watchlist.json）..."
    if command -v rsync &>/dev/null; then
        rsync -a --delete \
            --exclude="data/" \
            --exclude=".env" \
            --exclude="watchlist.json" \
            --exclude="env_quant/" \
            --exclude="logs/" \
            --exclude="exports/" \
            "${EXTRACTED_DIR}/" "${DEPLOY_DIR}/"
    else
        warn "rsync 未安装，使用 cp -r 方式（不会删除旧文件）"
        # 手动排除保护文件
        (
            cd "${EXTRACTED_DIR}"
            find . -not -path "./data*" \
                   -not -path "./.env" \
                   -not -path "./watchlist.json" \
                   -not -path "./env_quant*" \
                   -not -path "./logs*" \
                   -not -path "./exports*" \
                   -not -name "." \
                   | while read -r f; do
                if [[ -f "$f" ]]; then
                    dest_dir="${DEPLOY_DIR}/$(dirname "$f")"
                    mkdir -p "$dest_dir"
                    cp "$f" "${DEPLOY_DIR}/$f"
                fi
            done
        )
    fi
    success "代码文件同步完成"
fi

# ─── 创建运行时目录 ───────────────────────────────────────────
step "确保运行时目录存在"
mkdir -p "${DEPLOY_DIR}/data"
mkdir -p "${DEPLOY_DIR}/logs"
mkdir -p "${DEPLOY_DIR}/exports"
success "data/ logs/ exports/ 目录就绪"

# ─── Python 虚拟环境 ─────────────────────────────────────────
VENV_DIR="${DEPLOY_DIR}/env_quant"

if ! $IS_UPGRADE; then
    step "创建 Python 虚拟环境"
    info "使用 ${PYTHON_BIN} 创建 env_quant/..."
    "$PYTHON_BIN" -m venv "${VENV_DIR}"
    success "虚拟环境创建成功：${VENV_DIR}"
fi

step "安装/更新 Python 依赖"
info "pip install -r requirements.txt..."
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -r "${DEPLOY_DIR}/requirements.txt"
success "依赖安装完成"

# ─── 用户配置文件 ─────────────────────────────────────────────
step "检查用户配置文件"

ENV_FILE="${DEPLOY_DIR}/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    if [[ -f "${DEPLOY_DIR}/.env.example" ]]; then
        cp "${DEPLOY_DIR}/.env.example" "$ENV_FILE"
        warn ".env 不存在，已从 .env.example 复制"
        warn "请编辑 ${ENV_FILE} 填入实际配置（富途 OpenD 地址等）"
    else
        warn ".env 和 .env.example 均不存在，请手动创建 ${ENV_FILE}"
    fi
else
    success ".env 已存在，保持不变"
fi

WATCHLIST_FILE="${DEPLOY_DIR}/watchlist.json"
if [[ ! -f "$WATCHLIST_FILE" ]]; then
    if [[ -f "${DEPLOY_DIR}/watchlist.json.example" ]]; then
        cp "${DEPLOY_DIR}/watchlist.json.example" "$WATCHLIST_FILE"
        warn "watchlist.json 不存在，已从 watchlist.json.example 复制"
        warn "请编辑 ${WATCHLIST_FILE} 填入实际关注股票列表"
    else
        warn "watchlist.json 和 watchlist.json.example 均不存在，请手动创建"
    fi
else
    success "watchlist.json 已存在，保持不变"
fi

# ─── 设置脚本可执行权限 ──────────────────────────────────────
step "设置部署脚本可执行权限"
chmod +x "${DEPLOY_DIR}/deploy/deploy.sh" 2>/dev/null || true
chmod +x "${DEPLOY_DIR}/deploy/start.sh"  2>/dev/null || true
chmod +x "${DEPLOY_DIR}/deploy/stop.sh"   2>/dev/null || true
success "脚本权限设置完成"

# ─── 升级：重启服务 ──────────────────────────────────────────
if $IS_UPGRADE && $DO_RESTART; then
    step "重启服务"
    START_SCRIPT="${DEPLOY_DIR}/deploy/start.sh"
    if [[ -f "$START_SCRIPT" ]]; then
        bash "$START_SCRIPT"
    else
        warn "未找到 start.sh，请手动启动服务"
    fi
fi

# ─── 完成 ────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if $IS_UPGRADE; then
    echo -e "${GREEN}  升级完成！${NC}"
else
    echo -e "${GREEN}  首次部署完成！${NC}"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  部署目录：${DEPLOY_DIR}"
echo ""

if ! $IS_UPGRADE; then
    echo "  ── 下一步 ────────────────────────────────────────"
    echo "  1. 编辑配置文件："
    echo "       vi ${DEPLOY_DIR}/.env"
    echo "       vi ${DEPLOY_DIR}/watchlist.json"
    echo ""
    echo "  2. 启动富途 OpenD（打开富途牛牛客户端）"
    echo ""
    echo "  3. 启动服务："
    echo "       bash ${DEPLOY_DIR}/deploy/start.sh"
    echo ""
    echo "  4. 访问 Web 界面："
    echo "       http://localhost:8000"
fi

if $IS_UPGRADE && ! $DO_RESTART; then
    echo "  升级已完成，服务未自动重启。"
    echo "  如需重启，执行："
    echo "    bash ${DEPLOY_DIR}/deploy/stop.sh"
    echo "    bash ${DEPLOY_DIR}/deploy/start.sh"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
