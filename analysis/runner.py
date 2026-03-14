"""后台分析调度 — 线程池逐只评分"""

import threading
import time
from datetime import date
import pandas as pd
import streamlit as st
from ai.client import get_ai_client, call_ai
from ai.prompts_top10 import SYSTEM_SUMMARY, build_summary_prompt
from analysis.scorer import score_all, get_top_n


# ══════════════════════════════════════════════════════════════════════════════
# 每日缓存键
# ══════════════════════════════════════════════════════════════════════════════

def _cache_key(model_name: str) -> str:
    return f"top10_result_{date.today().isoformat()}_{model_name}"


def get_cached_result(model_name: str) -> pd.DataFrame | None:
    """获取今日缓存的评分结果"""
    key = _cache_key(model_name)
    return st.session_state.get(key)


def save_cached_result(model_name: str, df: pd.DataFrame):
    """缓存今日评分结果"""
    key = _cache_key(model_name)
    st.session_state[key] = df


# ══════════════════════════════════════════════════════════════════════════════
# 后台任务管理
# ══════════════════════════════════════════════════════════════════════════════

def get_job(ss) -> dict:
    """获取当前后台任务"""
    return ss.get("bg_job", {})


def is_running(ss) -> bool:
    return get_job(ss).get("status") == "running"


def is_done(ss) -> bool:
    return get_job(ss).get("status") == "done"


def start_scoring(ss, candidates_df: pd.DataFrame, model_name: str):
    """启动后台评分线程"""
    if is_running(ss):
        return  # 已在运行

    client, cfg, err = get_ai_client(model_name)
    if err:
        ss["bg_job"] = {"status": "done", "error": err, "progress": [f"❌ {err}"]}
        return

    job = {
        "status": "running",
        "progress": [],
        "error": None,
        "result": None,
        "model": model_name,
        "total": len(candidates_df),
        "current": 0,
    }
    ss["bg_job"] = job

    def _run():
        try:
            job["progress"].append(f"📊 开始逐只分析，共 {len(candidates_df)} 只候选股...")

            def progress_cb(current, total, msg):
                job["current"] = current
                job["progress"].append(f"[{current}/{total}] {msg}")

            scored = score_all(client, cfg, candidates_df,
                               model_name=model_name,
                               progress_callback=progress_cb)

            job["progress"].append(f"✅ 评分完成！共评分 {len(scored)} 只股票")
            job["result"] = scored

            # 生成总结报告
            job["progress"].append("📝 正在生成每日总结报告...")
            try:
                top10 = scored.head(10)
                stock_lines = []
                for _, r in top10.iterrows():
                    stock_lines.append(
                        f"- {r['股票名称']}({r['代码']}) 综合评分{r['综合评分']}/10"
                        f" 短线建议:{r.get('短线建议','未知')}"
                    )
                stocks_text = "\n".join(stock_lines)
                summary_prompt = build_summary_prompt(stocks_text, len(candidates_df))
                summary_text, s_err = call_ai(
                    client, cfg, summary_prompt,
                    system=SYSTEM_SUMMARY, max_tokens=4000
                )
                job["summary"] = summary_text if not s_err else f"总结生成失败：{s_err}"
            except Exception as se:
                job["summary"] = f"总结生成失败：{se}"

            job["progress"].append("✅ 全部完成！")
            job["status"] = "done"

            # 缓存结果
            save_cached_result(model_name, scored)

        except Exception as e:
            job["error"] = str(e)
            job["progress"].append(f"❌ 分析出错：{e}")
            job["status"] = "done"

    t = threading.Thread(target=_run, daemon=True)
    t.start()
