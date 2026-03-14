"""后台分析调度 — 数据增强 + 并行评分"""

import threading
from datetime import date
import pandas as pd
import streamlit as st
from ai.client import get_ai_client, call_ai
from ai.prompts_top10 import SYSTEM_SUMMARY, build_summary_prompt
from analysis.scorer import score_all


# ══════════════════════════════════════════════════════════════════════════════
# 每日缓存
# ══════════════════════════════════════════════════════════════════════════════

def _cache_key(model_name: str) -> str:
    return f"top10_result_{date.today().isoformat()}_{model_name}"


def _summary_key(model_name: str) -> str:
    return f"top10_summary_{date.today().isoformat()}_{model_name}"


def get_cached_result(model_name: str) -> pd.DataFrame | None:
    return st.session_state.get(_cache_key(model_name))


def get_cached_summary(model_name: str) -> str | None:
    return st.session_state.get(_summary_key(model_name))


def save_cached_result(model_name: str, df: pd.DataFrame, summary: str = ""):
    st.session_state[_cache_key(model_name)] = df
    if summary:
        st.session_state[_summary_key(model_name)] = summary


# ══════════════════════════════════════════════════════════════════════════════
# 后台任务管理
# ══════════════════════════════════════════════════════════════════════════════

def get_job(ss) -> dict:
    return ss.get("bg_job", {})


def is_running(ss) -> bool:
    return get_job(ss).get("status") == "running"


def is_done(ss) -> bool:
    return get_job(ss).get("status") == "done"


def start_scoring(ss, candidates_df: pd.DataFrame, model_name: str):
    """启动后台评分线程"""
    if is_running(ss):
        return

    client, cfg, err = get_ai_client(model_name)
    if err:
        ss["bg_job"] = {"status": "done", "error": err, "progress": [f"❌ {err}"]}
        return

    job = {
        "status": "running",
        "progress": [],
        "error": None,
        "result": None,
        "summary": None,
        "model": model_name,
        "total": len(candidates_df),
        "current": 0,
    }
    ss["bg_job"] = job

    def _run():
        try:
            # Phase 1: 数据增强
            job["progress"].append("📊 正在从 Tushare 获取增强数据（PE/PB/K线）...")
            try:
                from data.tushare_data import enrich_candidates, ts_ok
                if ts_ok():
                    enriched_df = enrich_candidates(
                        candidates_df,
                        progress_callback=lambda msg: job["progress"].append(f"  {msg}")
                    )
                    job["progress"].append(f"✅ 数据增强完成（行业/PE/PB/K线摘要）")
                else:
                    enriched_df = candidates_df
                    job["progress"].append("⚠️ Tushare 不可用，使用基础数据分析")
            except Exception as e:
                enriched_df = candidates_df
                job["progress"].append(f"⚠️ 数据增强失败({e})，使用基础数据")

            # Phase 2: 并行 AI 评分
            total = len(enriched_df)
            job["progress"].append(f"🤖 开始并行AI评分，共 {total} 只候选股（3路并发）...")

            def progress_cb(current, total, msg):
                job["current"] = current
                job["progress"].append(f"[{current}/{total}] {msg}")

            scored = score_all(client, cfg, enriched_df,
                               model_name=model_name,
                               progress_callback=progress_cb,
                               max_workers=3)

            job["progress"].append(f"✅ 评分完成！共评分 {len(scored)} 只股票")
            job["result"] = scored

            # Phase 3: 生成总结报告
            job["progress"].append("📝 正在生成每日总结报告...")
            summary = ""
            try:
                top10 = scored.head(10)
                stock_lines = []
                for _, r in top10.iterrows():
                    line = (f"- {r['股票名称']}({r['代码']}) "
                            f"行业:{r.get('行业','未知')} "
                            f"综合评分{r['综合评分']}/10 "
                            f"短线建议:{r.get('短线建议','未知')}")
                    stock_lines.append(line)
                stocks_text = "\n".join(stock_lines)
                summary_prompt = build_summary_prompt(stocks_text, total)
                summary, s_err = call_ai(
                    client, cfg, summary_prompt,
                    system=SYSTEM_SUMMARY, max_tokens=4000
                )
                if s_err:
                    summary = f"总结生成失败：{s_err}"
            except Exception as se:
                summary = f"总结生成失败：{se}"

            job["summary"] = summary
            job["progress"].append("✅ 全部完成！")
            job["status"] = "done"

            save_cached_result(model_name, scored, summary)

        except Exception as e:
            job["error"] = str(e)
            job["progress"].append(f"❌ 分析出错：{e}")
            job["status"] = "done"

    t = threading.Thread(target=_run, daemon=True)
    t.start()
