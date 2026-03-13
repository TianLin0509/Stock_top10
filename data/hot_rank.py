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
    """合并人气榜和成交额榜，去重，双榜股票标记为'双榜'"""
    if hot_df.empty and vol_df.empty:
        return pd.DataFrame()

    # 以人气榜为基础
    if not hot_df.empty:
        merged = hot_df[["代码", "股票名称", "最新价", "涨跌幅"]].copy()
        merged["来源"] = "人气榜"
        merged["人气排名"] = hot_df["排名"]
    else:
        merged = pd.DataFrame()

    # 处理成交额榜
    if not vol_df.empty:
        v = vol_df[["代码", "股票名称", "最新价", "涨跌幅"]].copy()
        v["成交额排名"] = vol_df["排名"]
        if "成交额(亿)" in vol_df.columns:
            v["成交额(亿)"] = vol_df["成交额(亿)"]

        if not merged.empty:
            # 双榜股票：补充成交额信息，标记为"双榜"
            both_mask = merged["代码"].isin(v["代码"])
            merged.loc[both_mask, "来源"] = "双榜"

            vol_info = v.set_index("代码")[["成交额排名"]].to_dict()["成交额排名"]
            merged["成交额排名"] = merged["代码"].map(vol_info)
            if "成交额(亿)" in v.columns:
                vol_amt = v.set_index("代码")["成交额(亿)"].to_dict()
                merged["成交额(亿)"] = merged["代码"].map(vol_amt)

            # 仅成交额榜的股票追加
            new_only = v[~v["代码"].isin(merged["代码"])].copy()
            if not new_only.empty:
                new_only["来源"] = "成交额榜"
                merged = pd.concat([merged, new_only], ignore_index=True)
        else:
            v["来源"] = "成交额榜"
            merged = v

    return merged.reset_index(drop=True)
