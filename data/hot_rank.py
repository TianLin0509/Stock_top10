"""数据获取 — 人气榜 + 成交额榜"""

import pandas as pd
import streamlit as st


@st.cache_data(ttl=1800, show_spinner=False)
def get_hot_rank(top_n: int = 100) -> tuple[pd.DataFrame, str | None]:
    """东方财富人气榜 Top N"""
    try:
        import akshare as ak
        df = ak.stock_hot_rank_em()
        if df is None or df.empty:
            return pd.DataFrame(), "人气榜数据为空"
        df = df.head(top_n)
        df.columns = ["排名", "代码", "股票名称", "最新价", "涨跌额", "涨跌幅"]
        # 代码标准化: SH600519 -> 600519
        df["代码"] = df["代码"].str.replace(r"^(SH|SZ|BJ)", "", regex=True)
        return df, None
    except Exception as e:
        return pd.DataFrame(), f"人气榜获取失败：{e}"


@st.cache_data(ttl=1800, show_spinner=False)
def get_hot_up_rank(top_n: int = 100) -> tuple[pd.DataFrame, str | None]:
    """东方财富飙升榜 Top N（人气飙升最快的股票）"""
    try:
        import akshare as ak
        df = ak.stock_hot_up_em()
        if df is None or df.empty:
            return pd.DataFrame(), "飙升榜数据为空"
        df = df.head(top_n)
        df.columns = ["昨日排名_今日排名_变动", "排名", "代码", "股票名称", "最新价", "涨跌额", "涨跌幅"]
        df["代码"] = df["代码"].str.replace(r"^(SH|SZ|BJ)", "", regex=True)
        return df[["排名", "代码", "股票名称", "最新价", "涨跌额", "涨跌幅"]], None
    except Exception as e:
        return pd.DataFrame(), f"飙升榜获取失败：{e}"


@st.cache_data(ttl=1800, show_spinner=False)
def get_volume_rank(top_n: int = 100) -> tuple[pd.DataFrame, str | None]:
    """成交额排名 Top N — 东方财富 HTTP 接口"""
    try:
        import requests as req
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1, "pz": top_n, "po": 1,
            "np": 1, "fltt": 2, "invt": 2,
            "fid": "f6",  # 按成交额排序
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f2,f3,f5,f6,f12,f14",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }
        resp = req.get(url, params=params, timeout=15)
        data = resp.json().get("data", {})
        items = data.get("diff", [])
        if not items:
            return pd.DataFrame(), "成交额榜数据为空"

        rows = []
        for i, item in enumerate(items, 1):
            rows.append({
                "排名": i,
                "代码": item.get("f12", ""),
                "股票名称": item.get("f14", ""),
                "最新价": item.get("f2", 0),
                "涨跌幅": item.get("f3", 0),
                "成交额(亿)": round(item.get("f6", 0) / 1e8, 2),
            })
        return pd.DataFrame(rows), None
    except Exception as e:
        # 备用方案：akshare
        return _get_volume_rank_akshare(top_n)


def _get_volume_rank_akshare(top_n: int) -> tuple[pd.DataFrame, str | None]:
    """akshare 备用方案获取成交额排名"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return pd.DataFrame(), "全量行情获取失败"
        df = df.sort_values("成交额", ascending=False).head(top_n).reset_index(drop=True)
        result = pd.DataFrame({
            "排名": range(1, len(df) + 1),
            "代码": df["代码"].values,
            "股票名称": df["名称"].values,
            "最新价": df["最新价"].values,
            "涨跌幅": df["涨跌幅"].values,
            "成交额(亿)": (df["成交额"] / 1e8).round(2).values,
        })
        return result, None
    except Exception as e:
        return pd.DataFrame(), f"成交额榜获取失败（备用方案也失败）：{e}"


def merge_candidates(hot_df: pd.DataFrame, vol_df: pd.DataFrame) -> pd.DataFrame:
    """合并人气榜和成交额榜，去重，标记来源"""
    dfs = []
    if not hot_df.empty:
        h = hot_df[["代码", "股票名称", "最新价", "涨跌幅"]].copy()
        h["来源"] = "人气榜"
        h["人气排名"] = hot_df["排名"]
        dfs.append(h)
    if not vol_df.empty:
        v = vol_df[["代码", "股票名称", "最新价", "涨跌幅"]].copy()
        v["来源"] = "成交额榜"
        v["成交额排名"] = vol_df["排名"]
        if "成交额(亿)" in vol_df.columns:
            v["成交额(亿)"] = vol_df["成交额(亿)"]
        dfs.append(v)

    if not dfs:
        return pd.DataFrame()

    merged = pd.concat(dfs, ignore_index=True)
    # 去重：保留第一个出现的（优先人气榜）
    merged = merged.drop_duplicates(subset=["代码"], keep="first").reset_index(drop=True)
    return merged
