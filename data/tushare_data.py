"""Tushare 数据增强 — 批量获取 PE/PB/市值/行业/K线摘要"""

import pandas as pd
import streamlit as st
import tushare as ts
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed


# ══════════════════════════════════════════════════════════════════════════════
# INIT（复用 Stock_test 的配置方式）
# ══════════════════════════════════════════════════════════════════════════════

TUSHARE_TOKEN = st.secrets.get("TUSHARE_TOKEN", "")
TUSHARE_URL = st.secrets.get("TUSHARE_URL", "http://lianghua.nanyangqiankun.top")


def _init_tushare():
    try:
        import time as _time
        import requests as _req

        ts.set_token(TUSHARE_TOKEN)
        p = ts.pro_api(TUSHARE_TOKEN)
        p._DataApi__token = TUSHARE_TOKEN
        p._DataApi__http_url = TUSHARE_URL

        _orig_post = _req.post
        def _patched_post(*a, **kw):
            kw.setdefault("timeout", 30)
            return _orig_post(*a, **kw)
        _req.post = _patched_post

        for attempt in range(1, 4):
            try:
                test = p.trade_cal(exchange="SSE", start_date="20240101", end_date="20240103")
                if test is not None and not test.empty:
                    return p, None
            except Exception:
                if attempt < 3:
                    _time.sleep(2)
        return None, "Tushare 连接失败"
    except Exception as e:
        return None, f"Tushare 初始化失败：{e}"


_pro, _ts_err = _init_tushare()


def ts_ok() -> bool:
    return _pro is not None


def get_ts_status() -> str:
    return "Tushare 可用" if _pro else (_ts_err or "不可用")


# ══════════════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════════════

def to_ts_code(code6: str) -> str:
    code6 = code6.strip()
    if "." in code6:
        return code6.upper()
    if code6.startswith("6"):
        return f"{code6}.SH"
    if code6.startswith(("4", "8")):
        return f"{code6}.BJ"
    return f"{code6}.SZ"


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _ndays_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y%m%d")


def _retry(fn, retries=3, delay=1):
    import time as _time
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            if attempt < retries:
                _time.sleep(delay)
                delay *= 2
            else:
                raise


# ══════════════════════════════════════════════════════════════════════════════
# 批量数据获取
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def _get_stock_industry() -> dict:
    """获取全市场股票行业分类 → {code6: industry}"""
    if not _pro:
        return {}
    try:
        df = _retry(lambda: _pro.stock_basic(
            exchange="", list_status="L",
            fields="ts_code,symbol,name,industry"
        ))
        if df is not None and not df.empty:
            return dict(zip(df["symbol"], df["industry"]))
    except Exception:
        pass
    return {}


@st.cache_data(ttl=600, show_spinner=False)
def _get_daily_basic_batch() -> pd.DataFrame:
    """批量获取当日估值数据（PE/PB/市值/换手率/量比）"""
    if not _pro:
        return pd.DataFrame()
    # 尝试最近5个交易日，找到最新有数据的日期
    for offset in range(5):
        trade_date = (datetime.now() - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            df = _retry(lambda td=trade_date: _pro.daily_basic(
                trade_date=td,
                fields="ts_code,close,pe_ttm,pb,total_mv,turnover_rate,volume_ratio"
            ))
            if df is not None and not df.empty:
                df["code6"] = df["ts_code"].str.split(".").str[0]
                return df
        except Exception:
            continue
    return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def _get_daily_batch() -> tuple[pd.DataFrame, str]:
    """批量获取当日全市场日线数据（含成交额），返回 (DataFrame, 交易日期)"""
    if not _pro:
        return pd.DataFrame(), ""
    for offset in range(5):
        trade_date = (datetime.now() - timedelta(days=offset)).strftime("%Y%m%d")
        try:
            df = _retry(lambda td=trade_date: _pro.daily(trade_date=td))
            if df is not None and not df.empty:
                df["code6"] = df["ts_code"].str.split(".").str[0]
                return df, trade_date
        except Exception:
            continue
    return pd.DataFrame(), ""


@st.cache_data(ttl=86400, show_spinner=False)
def _get_stock_names() -> dict:
    """全市场股票名称 → {code6: name}"""
    if not _pro:
        return {}
    try:
        df = _retry(lambda: _pro.stock_basic(
            exchange="", list_status="L", fields="symbol,name"
        ))
        if df is not None and not df.empty:
            return dict(zip(df["symbol"], df["name"]))
    except Exception:
        pass
    return {}


def _sv(v, d=2):
    """安全取值并四舍五入"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return 0
    return round(v, d)


def get_volume_rank_tushare(top_n: int) -> tuple[pd.DataFrame, str | None]:
    """Tushare 成交额排名 Top N"""
    daily, td = _get_daily_batch()
    if daily.empty:
        return pd.DataFrame(), "Tushare 日线数据不可用"

    top = daily.sort_values("amount", ascending=False).head(top_n).reset_index(drop=True)
    names = _get_stock_names()
    basic = _get_daily_basic_batch()

    # 构建查找字典
    tr_map, vr_map, pe_map, mv_map = {}, {}, {}, {}
    if not basic.empty:
        bi = basic.set_index("code6")
        if "turnover_rate" in bi.columns: tr_map = bi["turnover_rate"].to_dict()
        if "volume_ratio" in bi.columns: vr_map = bi["volume_ratio"].to_dict()
        if "pe_ttm" in bi.columns: pe_map = bi["pe_ttm"].to_dict()
        if "total_mv" in bi.columns: mv_map = bi["total_mv"].to_dict()

    rows = []
    for i, (_, r) in enumerate(top.iterrows(), 1):
        code = r["code6"]
        amt = r.get("amount", 0) or 0
        mv = mv_map.get(code)
        rows.append({
            "排名": i, "代码": code,
            "股票名称": names.get(code, ""),
            "最新价": _sv(r.get("close")),
            "涨跌幅": _sv(r.get("pct_chg")),
            "成交额(亿)": round(amt / 1e5, 2),
            "换手率": _sv(tr_map.get(code)),
            "量比": _sv(vr_map.get(code)),
            "市盈率": _sv(pe_map.get(code)),
            "总市值(亿)": _sv(mv, 1) / 10000 if mv and pd.notna(mv) else 0,
            "主力净流入(万)": 0,
        })
    return pd.DataFrame(rows), None


def get_all_volume_data_tushare() -> pd.DataFrame:
    """Tushare 全市场成交额排名数据"""
    daily, td = _get_daily_batch()
    if daily.empty:
        return pd.DataFrame()

    daily = daily.sort_values("amount", ascending=False).reset_index(drop=True)
    basic = _get_daily_basic_batch()
    basic_idx = basic.set_index("code6") if not basic.empty else pd.DataFrame()

    result = pd.DataFrame({
        "代码": daily["code6"].values,
        "成交额排名_all": range(1, len(daily) + 1),
        "成交额(亿)_all": (daily["amount"].fillna(0) / 1e5).round(2).values,
    })

    if not basic_idx.empty:
        for src, dst in [("turnover_rate", "换手率_all"), ("volume_ratio", "量比_all")]:
            if src in basic_idx.columns:
                result[dst] = result["代码"].map(basic_idx[src].to_dict()).fillna(0).round(2)
            else:
                result[dst] = 0
    else:
        result["换手率_all"] = 0
        result["量比_all"] = 0

    result["主力净流入(万)_all"] = 0
    return result


def _get_kline_summary(code6: str) -> str:
    """获取单只股票K线摘要（MA状态+近期走势）"""
    if not _pro:
        return ""
    ts_code = to_ts_code(code6)
    try:
        df = _retry(lambda: _pro.daily(
            ts_code=ts_code,
            start_date=_ndays_ago(90),
            end_date=_today()
        ))
        if df is None or df.empty:
            return ""
        df = df.sort_values("trade_date").reset_index(drop=True)
        df = df.rename(columns={
            "trade_date": "日期", "open": "开盘", "high": "最高",
            "low": "最低", "close": "收盘", "vol": "成交量",
            "pct_chg": "涨跌幅", "amount": "成交额",
        })
        return _price_summary(df)
    except Exception:
        return ""


def _price_summary(df: pd.DataFrame) -> str:
    """生成K线数据文本摘要"""
    if df.empty:
        return ""
    d = df.copy()
    for p in [5, 20, 60]:
        d[f"MA{p}"] = d["收盘"].rolling(p).mean()
    lt = d.iloc[-1]

    def pct(n):
        if len(d) <= n:
            return "N/A"
        return f"{(d.iloc[-1]['收盘'] / d.iloc[-n]['收盘'] - 1) * 100:.2f}%"

    ma5 = lt.get("MA5")
    ma20 = lt.get("MA20")
    ma60 = lt.get("MA60")
    if pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60):
        ma_arr = ("多头排列↑" if ma5 > ma20 > ma60
                  else "空头排列↓" if ma5 < ma20 < ma60
                  else "均线纠缠~")
        ma_line = f"MA5={ma5:.2f} MA20={ma20:.2f} MA60={ma60:.2f} → {ma_arr}"
    else:
        ma_line = "均线数据不足"

    lines = [
        f"最新收盘: {lt['收盘']:.2f}元",
        f"近期涨幅 5日:{pct(5)} 20日:{pct(20)} 60日:{pct(60)}",
        ma_line,
    ]
    if len(d) >= 20:
        lines.append(f"20日区间: 最高{d.tail(20)['最高'].max():.2f} / 最低{d.tail(20)['最低'].min():.2f}")

    # 近5日数据
    recent = d.tail(5)[["日期", "收盘", "涨跌幅", "成交量"]].to_string(index=False)
    lines.extend(["", "近5日行情：", recent])
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# 主入口：批量增强候选池
# ══════════════════════════════════════════════════════════════════════════════

def enrich_candidates(df: pd.DataFrame, progress_callback=None) -> pd.DataFrame:
    """
    对候选池批量补充 tushare 数据：
    - 行业、PE_TTM、PB、总市值、换手率、量比（批量一次获取）
    - K线摘要（并行获取）
    返回增强后的 DataFrame
    """
    if df.empty or not _pro:
        return df

    enriched = df.copy()
    codes = enriched["代码"].tolist()

    # 1. 批量：行业
    industry_map = _get_stock_industry()
    enriched["行业"] = enriched["代码"].map(industry_map)

    # 2. 批量：PE/PB/市值/换手率/量比（单次 API 调用获取全市场）
    basic_df = _get_daily_basic_batch()
    if not basic_df.empty:
        basic_indexed = basic_df.set_index("code6")
        for src_col, dst_col in [
            ("pe_ttm", "PE"),
            ("pb", "PB"),
            ("total_mv", "总市值(亿)"),
            ("turnover_rate", "换手率_ts"),
            ("volume_ratio", "量比_ts"),
        ]:
            if src_col in basic_indexed.columns:
                mapping = basic_indexed[src_col].to_dict()
                enriched[dst_col] = enriched["代码"].map(mapping)
        # 总市值单位转换：万 → 亿
        if "总市值(亿)" in enriched.columns:
            enriched["总市值(亿)"] = (enriched["总市值(亿)"] / 10000).round(1)
        # 用 tushare 数据覆盖 eastmoney 数据（更准确）
        if "换手率_ts" in enriched.columns:
            enriched["换手率"] = enriched["换手率_ts"].combine_first(
                enriched.get("换手率", pd.Series(dtype=float))
            )
            enriched.drop(columns=["换手率_ts"], inplace=True)
        if "量比_ts" in enriched.columns:
            enriched["量比"] = enriched["量比_ts"].combine_first(
                enriched.get("量比", pd.Series(dtype=float))
            )
            enriched.drop(columns=["量比_ts"], inplace=True)

    # 3. 并行获取K线摘要
    if progress_callback:
        progress_callback("正在获取K线数据...")

    kline_results = {}
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_get_kline_summary, code): code for code in codes}
        for future in as_completed(futures):
            code = futures[future]
            try:
                kline_results[code] = future.result()
            except Exception:
                kline_results[code] = ""

    enriched["K线摘要"] = enriched["代码"].map(kline_results)

    return enriched


# ══════════════════════════════════════════════════════════════════════════════
# 板块轮动信号
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800, show_spinner=False)
def get_sector_rotation() -> dict:
    """获取今日板块轮动信号：概念板块涨幅Top5 + 行业板块涨幅Top5"""
    result = {"概念板块": [], "行业板块": []}
    try:
        import akshare as ak
        # 概念板块（排除非传统概念：连板/打板/竞价等技术性标签）
        _EXCLUDE_KEYWORDS = [
            "连板", "打板", "竞价", "涨停", "跌停", "首板", "二板", "三板",
            "昨日", "炸板", "地天板", "天地板", "反包", "断板", "空间板",
        ]
        df_concept = ak.stock_board_concept_name_em()
        if df_concept is not None and not df_concept.empty:
            if "涨跌幅" in df_concept.columns and "板块名称" in df_concept.columns:
                df_concept["涨跌幅"] = pd.to_numeric(df_concept["涨跌幅"], errors="coerce")
                # 过滤掉技术性标签
                mask = df_concept["板块名称"].apply(
                    lambda x: not any(kw in str(x) for kw in _EXCLUDE_KEYWORDS)
                )
                df_filtered = df_concept[mask]
                top5 = df_filtered.nlargest(5, "涨跌幅")
                for _, row in top5.iterrows():
                    name = row.get("板块名称", "")
                    chg = row.get("涨跌幅", 0)
                    result["概念板块"].append(f"{name}({chg:+.2f}%)")

        # 行业板块
        df_industry = ak.stock_board_industry_name_em()
        if df_industry is not None and not df_industry.empty:
            if "涨跌幅" in df_industry.columns:
                df_industry["涨跌幅"] = pd.to_numeric(df_industry["涨跌幅"], errors="coerce")
                top5 = df_industry.nlargest(5, "涨跌幅")
                for _, row in top5.iterrows():
                    name = row.get("板块名称", "")
                    chg = row.get("涨跌幅", 0)
                    result["行业板块"].append(f"{name}({chg:+.2f}%)")
    except Exception:
        pass
    return result
