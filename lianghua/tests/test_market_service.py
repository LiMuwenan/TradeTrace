# -*- coding: utf-8 -*-
"""行情服务纯逻辑：代码归一化、区间校验、快照内容。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Stock
from app.services import market_service as svc


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/meta.db")
    Base.metadata.create_all(bind=engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def test_normalize_code_accepts_prefix_and_digits():
    assert svc.normalize_code("sh600519") == ("SH", "600519")
    assert svc.normalize_code("sh.600519") == ("SH", "600519")
    assert svc.normalize_code("600519") == ("SH", "600519")
    assert svc.normalize_code("000001") == ("SZ", "000001")
    assert svc.normalize_code("bj430047") == ("BJ", "430047")


def test_normalize_code_rejects_bad_input():
    with pytest.raises(ValueError):
        svc.normalize_code("60051")
    with pytest.raises(ValueError):
        svc.normalize_code("abc")


def test_build_snapshot_counts_real_rows(db):
    db.add_all([
        Stock(code="sh600519", name="贵州茅台", industry="白酒"),
        Stock(code="sz000001", name="平安银行", industry=""),
        Stock(code="bad-code", name="异常", industry=""),
    ])
    db.commit()
    out = svc.build_snapshot(db, "2026-10-25T02:30:00Z")
    assert out["generatedAt"] == "2026-10-25T02:30:00Z"
    assert out["count"] == 2                      # 异常行跳过，不造假
    assert [s["code"] for s in out["stocks"]] == ["000001", "600519"]
    assert out["stocks"][1] == {"code": "600519", "name": "贵州茅台", "market": "SH", "industry": "白酒"}


def test_build_snapshot_empty_db(db):
    out = svc.build_snapshot(db, "2026-10-25T02:30:00Z")
    assert out["count"] == 0 and out["stocks"] == []


def test_search_empty_query_returns_empty(db):
    db.add(Stock(code="sh600519", name="贵州茅台", industry=""))
    db.commit()
    assert svc.search_stocks(db, "  ") == []


def test_search_matches_code_and_name(db):
    db.add_all([
        Stock(code="sh600519", name="贵州茅台", industry="白酒"),
        Stock(code="sz000001", name="平安银行", industry=""),
    ])
    db.commit()
    assert [s["code"] for s in svc.search_stocks(db, "600519")] == ["600519"]
    assert [s["code"] for s in svc.search_stocks(db, "茅台")] == ["600519"]
    assert len(svc.search_stocks(db, "0")) == 2


def test_validate_range_errors():
    from app.errors import ApiError
    with pytest.raises(ApiError) as e1:
        svc.validate_range("2026-10-25", "2026-10-01")
    assert e1.value.code == "VALIDATION_ERROR"
    with pytest.raises(ApiError) as e2:
        svc.validate_range("2000-01-01", "2026-10-25")
    assert e2.value.code == "RANGE_TOO_LARGE"
    with pytest.raises(ApiError) as e3:
        svc.validate_range("2026/01/01", "")
    assert e3.value.code == "BAD_REQUEST"
    svc.validate_range("", "")          # 均缺省合法


def test_read_stock_kline_missing_file_returns_empty(tmp_path):
    class Cfg:
        data_dir = tmp_path
    out = svc.read_stock_kline(Cfg(), "600519", "", "")
    assert out["code"] == "600519" and out["market"] == "SH"
    assert out["raw"]["dates"] == [] and out["qfq"]["close"] == []


def test_read_index_kline_from_parquet(tmp_path):
    import pandas as pd
    from app.services import index_store
    df = pd.DataFrame([
        {"date": "2026-10-22", "code": "sh000300", "open": 1, "high": 2,
         "low": 1, "close": 1.5, "volume": 10},
        {"date": "2026-10-23", "code": "sh000300", "open": 2, "high": 3,
         "low": 2, "close": 2.5, "volume": 20},
    ])
    index_store.write_index(tmp_path, "sh000300", df)

    class Cfg:
        index_dir = tmp_path
    out = svc.read_index_kline(Cfg(), "sh000300", "2026-10-23", "")
    assert out["name"] == "沪深300"
    assert out["dates"] == ["2026-10-23"]
    assert out["close"] == [2.5]
