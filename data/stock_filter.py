"""量化初筛 — 过滤不适合短线的标的"""

import pandas as pd
import streamlit as st


@st.cache_data(ttl=86400, show_spinner=False)
def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    """对候选池做量化初筛，返回过滤后的 DataFrame"""
    if df.empty:
        return df

    filtered = df.copy()

    # 1. 排除 ST / *ST / 退市股
    mask_st = filtered["股票名称"].str.contains(r"ST|退市", case=False, na=False)
    filtered = filtered[~mask_st]

    # 2. 排除北交所 (代码8开头) 和科创板 (688开头) — 流动性/交易规则不同
    mask_bj = filtered["代码"].str.startswith("8")
    mask_kc = filtered["代码"].str.startswith("688")
    filtered = filtered[~mask_bj & ~mask_kc]

    # 3. 排除涨跌幅异常 — 涨停或跌停的追高风险大
    # 涨跌幅 > 9.8% 可能是涨停，< -9.8% 是跌停
    if "涨跌幅" in filtered.columns:
        filtered["涨跌幅"] = pd.to_numeric(filtered["涨跌幅"], errors="coerce")
        # 不排除涨停，因为人气榜里涨停股可能有连板预期
        # 但排除跌停股
        mask_down_limit = filtered["涨跌幅"] < -9.5
        filtered = filtered[~mask_down_limit]

    # 4. 排除价格过低 (< 2元) 的低价股 — 基本面差
    if "最新价" in filtered.columns:
        filtered["最新价"] = pd.to_numeric(filtered["最新价"], errors="coerce")
        mask_low = filtered["最新价"] < 2
        filtered = filtered[~mask_low]

    filtered = filtered.reset_index(drop=True)
    return filtered


def get_filter_summary(before: int, after: int) -> str:
    """返回过滤摘要文本"""
    removed = before - after
    return f"初筛：{before} → {after}（过滤 {removed} 只：ST/退市、北交所/科创板、跌停、低价股）"
