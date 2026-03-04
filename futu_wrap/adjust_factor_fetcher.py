import logging
from typing import List

from futu import RET_OK

from futu_wrap.client import FutuClient
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
        解析富途 get_rehab 返回的 DataFrame。

        富途前复权公式：adj_price = raw_price × forward_adj_factorA + forward_adj_factorB
        - forward_adj_factorA：乘法系数，拆送股时 < 1.0，纯分红时 = 1.0
        - forward_adj_factorB：加法偏移，现金分红时为负值（如 -1.0 HKD），无分红时 = 0.0
        """
        factors: List[AdjustFactor] = []

        for _, row in df.iterrows():
            try:
                ex_date = str(row.get("ex_div_date", row.get("time", "")))[:10]
                if not ex_date or ex_date == "nan":
                    continue

                fwd_a = float(row["forward_adj_factorA"])
                fwd_b = float(row["forward_adj_factorB"])
                bwd_a = float(row["backward_adj_factorA"])
                bwd_b = float(row["backward_adj_factorB"])

                factors.append(AdjustFactor(
                    stock_code=stock_code,
                    ex_date=ex_date,
                    forward_factor=fwd_a,
                    forward_factor_b=fwd_b,
                    backward_factor=bwd_a,
                    backward_factor_b=bwd_b,
                    factor_source="futu",
                ))
            except (KeyError, ValueError, TypeError) as e:
                logger.warning("Failed to parse rehab row: %s, error: %s", dict(row), e)

        factors.sort(key=lambda f: f.ex_date)
        return factors
