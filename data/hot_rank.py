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
            "fields": "f2,f3,f5,f6,f8,f9,f10,f12,f14,f20,f23,f62",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }
        resp = req.get(url, params=params, timeout=15)
        data = resp.json().get("data", {})
        items = data.get("diff", [])
        if not items:
            return pd.DataFrame(), "成交额榜数据为空"

        def _safe_num(v, default=0):
            if v is None or v == "-" or isinstance(v, str):
                return default
            return v

        rows = []
        for i, item in enumerate(items, 1):
            net_flow = _safe_num(item.get("f62", 0))
            mkt_cap = _safe_num(item.get("f20", 0))
            rows.append({
                "排名": i,
                "代码": item.get("f12", ""),
                "股票名称": item.get("f14", ""),
                "最新价": item.get("f2", 0),
                "涨跌幅": item.get("f3", 0),
                "成交额(亿)": round(_safe_num(item.get("f6", 0)) / 1e8, 2),
                "换手率": _safe_num(item.get("f8", 0)),
                "量比": _safe_num(item.get("f10", 0)),
                "市盈率": _safe_num(item.get("f9", 0)),
                "总市值(亿)": round(mkt_cap / 1e8, 1) if mkt_cap else 0,
                "主力净流入(万)": round(net_flow / 1e4, 2) if net_flow else 0,
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

            v_indexed = v.set_index("代码")
            merged["成交额排名"] = merged["代码"].map(v_indexed["成交额排名"].to_dict())
            for col in ["成交额(亿)", "换手率", "量比", "市盈率", "总市值(亿)", "主力净流入(万)"]:
                if col in v.columns:
                    merged[col] = merged["代码"].map(v_indexed[col].to_dict())

            # 仅成交额榜的股票追加
            new_only = v[~v["代码"].isin(merged["代码"])].copy()
            if not new_only.empty:
                new_only["来源"] = "成交额榜"
                merged = pd.concat([merged, new_only], ignore_index=True)
        else:
            v["来源"] = "成交额榜"
            merged = v

    # 为缺少成交额的股票（仅人气榜来源）补充数据
    merged = _fill_missing_volume(merged)

    return merged.reset_index(drop=True)


def _fill_missing_volume(df: pd.DataFrame) -> pd.DataFrame:
    """为缺少成交额的股票从东方财富批量获取成交额"""
    if df.empty:
        return df
    missing = df["成交额(亿)"].isna() | (df["成交额(亿)"] == 0) if "成交额(亿)" in df.columns else pd.Series([True] * len(df))
    if not missing.any():
        return df

    codes_need = df.loc[missing, "代码"].tolist()
    if not codes_need:
        return df

    try:
        import requests as req
        # 批量获取全 A 股成交额（取 Top 500 覆盖所有候选）
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": 1, "pz": 500, "po": 1,
            "np": 1, "fltt": 2, "invt": 2,
            "fid": "f6",
            "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
            "fields": "f6,f8,f10,f12,f62",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        }
        resp = req.get(url, params=params, timeout=10)
        items = resp.json().get("data", {}).get("diff", [])
        if items:
            vol_map = {}
            turnover_map = {}
            ratio_map = {}
            flow_map = {}
            for item in items:
                code = item.get("f12", "")
                f6 = item.get("f6", 0)
                if code and f6 and f6 != "-":
                    vol_map[code] = round(float(f6) / 1e8, 2)
                f8 = item.get("f8", 0)
                if f8 and f8 != "-":
                    turnover_map[code] = f8
                f10 = item.get("f10", 0)
                if f10 and f10 != "-":
                    ratio_map[code] = f10
                f62 = item.get("f62", 0)
                if f62 and f62 != "-":
                    flow_map[code] = round(float(f62) / 1e4, 2)

            for col, mapping in [("成交额(亿)", vol_map), ("换手率", turnover_map),
                                  ("量比", ratio_map), ("主力净流入(万)", flow_map)]:
                if col not in df.columns:
                    df[col] = None
                mask = df[col].isna() | (df[col] == 0)
                df.loc[mask, col] = df.loc[mask, "代码"].map(mapping)
    except Exception:
        pass
    return df
