"""逐只评分 + 排名"""

import re
import pandas as pd
import streamlit as st
from ai.client import call_ai, get_ai_client
from ai.prompts_top10 import SYSTEM_SCORER, build_score_prompt


def _parse_score(text: str) -> float:
    """从 AI 回复中提取综合评分"""
    # 匹配 "综合评分：8.5/10" 或 "综合评分: 8.5/10" 等
    m = re.search(r"综合评分[：:]\s*(\d+\.?\d*)\s*/\s*10", text)
    if m:
        return float(m.group(1))
    # 备用：匹配任何 X.X/10
    m = re.search(r"(\d+\.?\d*)\s*/\s*10", text)
    if m:
        return float(m.group(1))
    return 0.0


def score_single_stock(client, cfg, row: pd.Series,
                       model_name: str = "") -> dict:
    """对单只股票进行 AI 评分，返回结果字典"""
    code = str(row.get("代码", ""))
    name = str(row.get("股票名称", ""))
    price = row.get("最新价", 0)
    change = row.get("涨跌幅", 0)
    hot_rank = row.get("人气排名") if "人气排名" in row.index else None
    vol_rank = row.get("成交额排名") if "成交额排名" in row.index else None
    volume_yi = row.get("成交额(亿)") if "成交额(亿)" in row.index else None

    # 转换类型
    try:
        price = float(price)
    except (ValueError, TypeError):
        price = 0.0
    try:
        change = float(change)
    except (ValueError, TypeError):
        change = 0.0
    if hot_rank is not None:
        try:
            hot_rank = int(hot_rank)
        except (ValueError, TypeError):
            hot_rank = None
    if vol_rank is not None:
        try:
            vol_rank = int(vol_rank)
        except (ValueError, TypeError):
            vol_rank = None
    if volume_yi is not None:
        try:
            volume_yi = float(volume_yi)
        except (ValueError, TypeError):
            volume_yi = None

    prompt = build_score_prompt(code, name, price, change,
                                hot_rank, vol_rank, volume_yi)
    text, err = call_ai(client, cfg, prompt,
                        system=SYSTEM_SCORER, max_tokens=4000)

    score = _parse_score(text) if not err else 0.0

    return {
        "代码": code,
        "股票名称": name,
        "最新价": price,
        "涨跌幅": change,
        "综合评分": score,
        "AI分析": text if not err else f"分析失败：{err}",
        "模型": model_name,
        "人气排名": hot_rank,
        "成交额排名": vol_rank,
    }


def score_all(client, cfg, df: pd.DataFrame,
              model_name: str = "",
              progress_callback=None) -> pd.DataFrame:
    """对整个候选池逐只评分，返回按评分排序的 DataFrame"""
    results = []
    total = len(df)

    for i, (_, row) in enumerate(df.iterrows()):
        if progress_callback:
            progress_callback(i + 1, total,
                              f"正在分析 {row['股票名称']}（{row['代码']}）...")
        result = score_single_stock(client, cfg, row, model_name)
        results.append(result)

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("综合评分", ascending=False).reset_index(drop=True)
    result_df.index = result_df.index + 1  # 排名从1开始
    result_df.index.name = "推荐排名"
    return result_df


def get_top_n(scored_df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """取评分最高的 N 只"""
    if scored_df.empty:
        return scored_df
    return scored_df.head(n)
