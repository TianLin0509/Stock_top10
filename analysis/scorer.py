"""逐只评分 + 排名"""

import re
import pandas as pd
import streamlit as st
from ai.client import call_ai, get_ai_client
from ai.prompts_top10 import SYSTEM_SCORER, build_score_prompt


def _parse_score(text: str) -> float:
    """从 AI 回复中提取综合评分"""
    m = re.search(r"综合评分[：:]\s*(\d+\.?\d*)\s*/\s*10", text)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+\.?\d*)\s*/\s*10", text)
    if m:
        return float(m.group(1))
    return 0.0


def _parse_sub_scores(text: str) -> dict:
    """从 AI 回复中提取三项子评分"""
    scores = {}
    for label in ["基本面", "题材热度", "技术面"]:
        m = re.search(rf"{label}\s*\|\s*(\d+\.?\d*)\s*/\s*10", text)
        if m:
            scores[label] = float(m.group(1))
    return scores


def _parse_advice(text: str) -> str:
    """从 AI 回复中提取短线建议"""
    m = re.search(r"短线建议[：:]\s*[*]*\s*(强烈推荐|推荐|观望|回避)", text)
    if m:
        return m.group(1)
    return ""


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
    turnover_rate = row.get("换手率") if "换手率" in row.index else None
    volume_ratio = row.get("量比") if "量比" in row.index else None
    net_flow_wan = row.get("主力净流入(万)") if "主力净流入(万)" in row.index else None

    # 转换类型
    def _safe_float(v):
        if v is None:
            return None
        try:
            import math
            val = float(v)
            return None if math.isnan(val) else val
        except (ValueError, TypeError):
            return None

    def _safe_int(v):
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    price = _safe_float(price) or 0.0
    change = _safe_float(change) or 0.0
    hot_rank = _safe_int(hot_rank)
    vol_rank = _safe_int(vol_rank)
    volume_yi = _safe_float(volume_yi)
    turnover_rate = _safe_float(turnover_rate)
    volume_ratio = _safe_float(volume_ratio)
    net_flow_wan = _safe_float(net_flow_wan)

    prompt = build_score_prompt(code, name, price, change,
                                hot_rank, vol_rank, volume_yi,
                                turnover_rate, volume_ratio, net_flow_wan)
    text, err = call_ai(client, cfg, prompt,
                        system=SYSTEM_SCORER, max_tokens=4000)

    score = _parse_score(text) if not err else 0.0
    sub_scores = _parse_sub_scores(text) if not err else {}
    advice = _parse_advice(text) if not err else ""

    return {
        "代码": code,
        "股票名称": name,
        "最新价": price,
        "涨跌幅": change,
        "综合评分": score,
        "基本面": sub_scores.get("基本面"),
        "题材热度": sub_scores.get("题材热度"),
        "技术面": sub_scores.get("技术面"),
        "短线建议": advice,
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
