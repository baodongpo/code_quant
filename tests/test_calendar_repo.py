"""
tests/test_calendar_repo.py — CalendarRepository.has_calendar 单元测试

覆盖 BUG-01 修复场景：
  1. 空数据库 → False
  2. 数据覆盖到 end_date 当天 → True
  3. 数据覆盖到 end_date 之后 → True
  4. 数据覆盖不到 end_date（缺近期数据） → False（BUG-01 核心场景）
  5. end_date 恰好是周末（非交易日），最大交易日在 end_date 之前 → False（触发增量补充，幂等）
"""

import sqlite3
import tempfile
import os
import pytest

from db.schema import init_db
from db.repositories.calendar_repo import CalendarRepository


@pytest.fixture
def db_path(tmp_path):
    """创建临时 SQLite 数据库，初始化 Schema。"""
    path = str(tmp_path / "test_quant.db")
    init_db(path)
    return path


@pytest.fixture
def repo(db_path):
    return CalendarRepository(db_path)


class TestHasCalendar:
    """has_calendar() BUG-01 修复验证。"""

    def test_empty_db_returns_false(self, repo):
        """场景1：空数据库，任意范围均返回 False。"""
        assert repo.has_calendar("SH", "2024-01-01", "2024-12-31") is False

    def test_data_covers_end_date_exactly(self, repo):
        """场景2：最大交易日 == end_date → True。"""
        repo.insert_many("SH", ["2024-01-02", "2024-01-03", "2024-01-04"])
        assert repo.has_calendar("SH", "2024-01-01", "2024-01-04") is True

    def test_data_covers_beyond_end_date(self, repo):
        """场景3：最大交易日 > end_date → True。"""
        repo.insert_many("SH", ["2024-01-02", "2024-01-03", "2024-12-31"])
        assert repo.has_calendar("SH", "2024-01-01", "2024-06-30") is True

    def test_data_does_not_reach_end_date(self, repo):
        """
        场景4（BUG-01 核心）：DB 已有历史数据但未覆盖到 end_date。

        旧实现：COUNT > 0 → True（错误：会跳过增量补充）
        新实现：MAX(trade_date) < end_date → False（正确：触发增量拉取）
        """
        # 模拟历史数据已存在，但最新只到 2024-03-01，end_date 为今天
        repo.insert_many("SH", [
            "2024-01-02", "2024-01-03", "2024-01-04",
            "2024-02-01", "2024-02-02",
            "2024-03-01",
        ])
        # 请求范围要求覆盖到 2026-03-19（近期），DB 最新是 2024-03-01
        assert repo.has_calendar("SH", "2000-01-01", "2026-03-19") is False

    def test_end_date_is_weekend_last_trading_day_before(self, repo):
        """
        场景5（发现-01 核心）：DB 中除交易日外还存有 is_trading_day=0 的记录
        （如节假日补录），has_calendar 必须忽略这些记录，只基于交易日计算 MAX。

        旧 SQL：WHERE market=?  → MAX 包含非交易日 → 可能误返回 True
        新 SQL：WHERE market=? AND is_trading_day=1 → MAX 仅看交易日 → 返回 False
        """
        # 2024-01-05（周五）是最后一个交易日
        repo.insert_many("SH", ["2024-01-03", "2024-01-04", "2024-01-05"])
        # 额外插入一条 is_trading_day=0 的记录，日期更晚（2024-01-06 周六）
        repo.insert_many("SH", ["2024-01-06"], is_trading=False)
        # end_date = 2024-01-07（周日）
        # 旧实现：MAX 含 2024-01-06 → 2024-01-06 < 2024-01-07 → 仍 False（恰好不触发）
        # 更强验证：end_date = 2024-01-06，旧实现 MAX=2024-01-06 >= 2024-01-06 → True（误判）
        #           新实现：MAX trading only = 2024-01-05 < 2024-01-06 → False（正确）
        assert repo.has_calendar("SH", "2024-01-01", "2024-01-06") is False

    def test_different_markets_are_independent(self, repo):
        """不同市场的日历数据互不影响。"""
        repo.insert_many("SH", ["2024-06-03", "2024-06-04", "2024-06-05"])
        # HK 市场未写入任何数据
        assert repo.has_calendar("SH", "2024-01-01", "2024-06-05") is True
        assert repo.has_calendar("HK", "2024-01-01", "2024-06-05") is False

    def test_start_date_ignored_only_end_date_matters(self, repo):
        """
        has_calendar 检查全局 MAX(trade_date)，start_date 参数保留兼容但不影响判断。
        只要 MAX >= end_date 即视为覆盖充分。
        """
        repo.insert_many("SH", ["2020-01-02", "2024-06-28"])
        # 查询范围 start_date=2023-01-01，end_date=2024-06-28，最大值刚好 ==
        assert repo.has_calendar("SH", "2023-01-01", "2024-06-28") is True
