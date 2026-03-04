import json
import logging
from typing import List, Tuple

from config.settings import WATCHLIST_PATH
from db.repositories.stock_repo import StockRepository
from db.repositories.sync_meta_repo import SyncMetaRepository
from models.stock import Stock
from config.settings import ALL_PERIODS

logger = logging.getLogger(__name__)


class WatchlistManager:
    """
    管理 watchlist.json 与数据库 stocks 表的同步。
    差异检测：新增、重新激活、停用。
    """

    def __init__(
        self,
        stock_repo: StockRepository,
        sync_meta_repo: SyncMetaRepository,
        watchlist_path: str = WATCHLIST_PATH,
    ):
        self._stock_repo = stock_repo
        self._sync_meta_repo = sync_meta_repo
        self._watchlist_path = watchlist_path

    def load(self) -> Tuple[List[Stock], List[Stock], List[Stock]]:
        """
        读取 watchlist.json，与 DB 对比，执行差异同步。

        返回三元组：
          - active_stocks: 当前活跃的股票列表
          - newly_added:   本次新增的股票（DB 中不存在）
          - reactivated:   本次重新激活的股票（is_active 0→1）
        """
        json_stocks = self._load_json()
        db_stocks = {s.stock_code: s for s in self._stock_repo.get_all()}

        newly_added: List[Stock] = []
        reactivated: List[Stock] = []
        to_deactivate: List[str] = []

        json_active_codes = {s.stock_code for s in json_stocks if s.is_active}
        json_inactive_codes = {s.stock_code for s in json_stocks if not s.is_active}
        json_codes = {s.stock_code for s in json_stocks}

        for stock in json_stocks:
            db_stock = db_stocks.get(stock.stock_code)

            if db_stock is None:
                # 新增：DB 中不存在
                if stock.is_active:
                    newly_added.append(stock)
                    logger.info("New stock detected: %s", stock.stock_code)
            else:
                # 已存在：检查激活状态变化
                if not db_stock.is_active and stock.is_active:
                    # 重新激活：0 → 1
                    reactivated.append(stock)
                    logger.info("Stock reactivated: %s", stock.stock_code)
                elif db_stock.is_active and not stock.is_active:
                    # 停用：1 → 0
                    to_deactivate.append(stock.stock_code)
                    logger.info("Stock deactivated: %s", stock.stock_code)

        # DB 中存在但 JSON 中不存在的股票 → 停用
        for code in db_stocks:
            if code not in json_codes:
                if db_stocks[code].is_active:
                    to_deactivate.append(code)
                    logger.info("Stock removed from watchlist, deactivating: %s", code)

        # 批量 upsert 所有 JSON 中的股票到 DB
        self._stock_repo.upsert_many(json_stocks)

        # 停用不在 JSON 或 JSON 中标记为不活跃的股票
        for code in to_deactivate:
            self._stock_repo.set_active(code, False)

        # 确保新增股票的 sync_metadata 存在（pending 状态）
        for stock in newly_added + reactivated:
            for period in ALL_PERIODS:
                self._sync_meta_repo.ensure_exists(stock.stock_code, period)

        active_stocks = [s for s in json_stocks if s.is_active]
        logger.info(
            "Watchlist loaded: %d active, %d newly_added, %d reactivated, %d deactivated",
            len(active_stocks), len(newly_added), len(reactivated), len(to_deactivate)
        )
        return active_stocks, newly_added, reactivated

    def _load_json(self) -> List[Stock]:
        try:
            with open(self._watchlist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            logger.error("watchlist.json not found at %s", self._watchlist_path)
            return []
        except json.JSONDecodeError as e:
            logger.error("watchlist.json parse error: %s", e)
            return []

        stocks = []
        for market_node in data.get("markets", []):
            market = market_node.get("market", "")
            market_enabled = bool(market_node.get("enabled", True))
            for item in market_node.get("stocks", []):
                try:
                    stock_active = bool(item.get("is_active", True))
                    stocks.append(Stock(
                        stock_code=item["stock_code"],
                        market=market,
                        asset_type=item["asset_type"],
                        is_active=market_enabled and stock_active,
                        lot_size=int(item.get("lot_size", 1)),
                        currency=item["currency"],
                    ))
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning("Invalid watchlist entry %s: %s", item, e)
        return stocks
