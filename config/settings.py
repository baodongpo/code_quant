import os
from dotenv import load_dotenv

# 优先加载项目根目录下的 .env 文件（本地开发用，不提交仓库）
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BASE_DIR, ".env"))

# ============================================================
# OpenD 连接配置（从环境变量读取，fallback 到本地默认值）
# ============================================================
OPEND_HOST = os.getenv("OPEND_HOST", "127.0.0.1")
OPEND_PORT = int(os.getenv("OPEND_PORT", "11111"))

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = _BASE_DIR
DB_PATH = os.getenv("DB_PATH", os.path.join(BASE_DIR, "data", "quant.db"))
LOG_DIR = os.path.join(BASE_DIR, "logs")
WATCHLIST_PATH = os.path.join(BASE_DIR, "watchlist.json")

# ============================================================
# 历史K线查询限频参数（双约束，仅作用于 get_history_kline）
# ============================================================
RATE_LIMIT_MIN_INTERVAL = float(os.getenv("RATE_LIMIT_MIN_INTERVAL", "0.5"))   # 每次请求最小间隔（秒）
RATE_LIMIT_WINDOW_SECONDS = float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "30")) # 滑动窗口大小（秒）
RATE_LIMIT_MAX_IN_WINDOW = int(os.getenv("RATE_LIMIT_MAX_IN_WINDOW", "25"))     # 窗口内最大请求数
RATE_LIMIT_MAX_RETRIES = int(os.getenv("RATE_LIMIT_MAX_RETRIES", "3"))          # 最大重试次数

# ============================================================
# 通用富途接口限频参数（所有非K线接口：日历、复权因子等）
# 富途全局限制：30s 内所有接口调用总次数不超过 60 次
# K线限频器默认 25次/30s + 通用限频器默认 35次/30s = 60次/30s，恰好不超上限
# ============================================================
GENERAL_RATE_LIMIT_WINDOW_SECONDS = float(os.getenv("GENERAL_RATE_LIMIT_WINDOW_SECONDS", "30"))
GENERAL_RATE_LIMIT_MAX_IN_WINDOW = int(os.getenv("GENERAL_RATE_LIMIT_MAX_IN_WINDOW", "35"))

# ============================================================
# 订阅额度上限
# ============================================================
MAX_SUBSCRIPTIONS = int(os.getenv("MAX_SUBSCRIPTIONS", "100"))  # 基础版最大订阅股票数

# ============================================================
# 历史拉取起始日（新增股票全量同步起点）
# ============================================================
DEFAULT_HISTORY_START = os.getenv("DEFAULT_HISTORY_START", "2000-01-01")

# ============================================================
# K线粒度列表（从 Period 枚举派生，保持单一来源）
# ============================================================
from models.enums import Period
ALL_PERIODS = [p.value for p in Period]

# ============================================================
# A股日历查询市场映射（A股用 SH 日历作为基准）
# ============================================================
A_STOCK_CALENDAR_MARKET = "SH"

# ============================================================
# 数据导出配置
# ============================================================
EXPORT_DIR = os.getenv("EXPORT_DIR", os.path.join(BASE_DIR, "exports"))

# ============================================================
# 服务化配置（模块C：常驻进程、断线重连、健康检查）
# ============================================================
RECONNECT_MAX_RETRIES = int(os.getenv("RECONNECT_MAX_RETRIES", "5"))
RECONNECT_BASE_INTERVAL = int(os.getenv("RECONNECT_BASE_INTERVAL", "30"))
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))
HEALTH_FILE = os.getenv("HEALTH_FILE", os.path.join(BASE_DIR, "data", "health.json"))

# ============================================================
# Web 访问控制配置（迭代5新增：局域网访问 + Token 鉴权）
# ============================================================
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")          # uvicorn 绑定地址，0.0.0.0 开放局域网
WEB_ACCESS_TOKEN = os.getenv("WEB_ACCESS_TOKEN", "")   # 访问 Token，留空不启用鉴权

# ============================================================
# 系统版本号（硬编码，随代码发布更新，不依赖 .env 配置文件）
# ============================================================
APP_VERSION = "v0.8.3"
