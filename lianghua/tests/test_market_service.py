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
