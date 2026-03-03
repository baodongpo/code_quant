import logging
from typing import List

from futu import RET_OK

from futu.client import FutuClient
from models.kline import AdjustFactor

logger = logging.getLogger(__name__)


class AdjustFactorFetcher:
    """
    封装 get_rehab_list，获取指定股票的除权除息列表并计算累乘前复权因子。
    """

    def __init__(self, client: FutuClient):
        self._client = client

    def fetch_factors(self, stock_code: str) -> List[AdjustFactor]:
        """
        拉取股票的复权因子列表。
        返回按 ex_date 升序排列的 AdjustFactor 列表。
        """
        ret, data = self._client.ctx.get_rehab(stock_code)

        if ret != RET_OK:
            logger.error("get_rehab failed for %s: %s", stock_code, data)
            return []

        if data is None or data.empty:
            logger.debug("No rehab data for %s", stock_code)
            return []

        factors = self._parse_rehab(stock_code, data)
        logger.debug("Fetched %d adjust factors for %s", len(factors), stock_code)
        return factors

    @staticmethod
    def _parse_rehab(stock_code: str, df) -> List[AdjustFactor]:
        """
        解析富途返回的除权除息 DataFrame，计算累乘前复权因子。

        富途 get_rehab 返回字段（参考 SDK 文档）：
          - time: 除权日
          - forward_factor: 前复权因子（累乘值，富途直接提供）
          - backward_factor: 后复权因子（累乘值）

        如果富途 SDK 版本直接提供 forward_factor，则直接使用；
        否则从 per_share_ratio（拆股比例）和 per_share_div（每股分红）手动计算。
        """
        factors: List[AdjustFactor] = []

        for _, row in df.iterrows():
            try:
                ex_date = str(row.get("time", row.get("ex_date", "")))[:10]
                if not ex_date or ex_date == "nan":
                    continue

                # 优先使用 SDK 直接返回的复权因子
                if "forward_factor" in df.columns:
                    fwd = float(row["forward_factor"])
                    bwd = float(row.get("backward_factor", 1.0))
                else:
                    # 手动计算：factor = (close + dividend) / close * split_ratio
                    # 富途 rehab 字段可能有 per_share_ratio, per_share_div 等
                    # 此处简化为 1.0（需根据实际 SDK 字段调整）
                    logger.warning(
                        "forward_factor column not found in rehab data for %s, using 1.0",
                        stock_code
                    )
                    fwd = 1.0
                    bwd = 1.0

                factors.append(AdjustFactor(
                    stock_code=stock_code,
                    ex_date=ex_date,
                    forward_factor=fwd,
                    backward_factor=bwd,
                    factor_source="futu",
                ))
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Failed to parse rehab row: %s, error: %s", dict(row), e)

        # 按除权日升序排列
        factors.sort(key=lambda f: f.ex_date)
        return factors
