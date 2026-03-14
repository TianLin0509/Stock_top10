"""Stock Top 10 — 每日人气+成交额 Top 100 → AI 精选 Top 10"""

import time
import streamlit as st

st.set_page_config(
    page_title="每日 Top10 精选",
    page_icon="🏆",
    layout="wide",
)

from config import MODEL_CONFIGS, MODEL_NAMES
from ai.client import get_token_usage, reset_token_usage
from data.hot_rank import get_hot_rank, get_volume_rank, merge_candidates
from data.stock_filter import apply_filters, get_filter_summary
from analysis.runner import (
    get_cached_result, get_cached_summary, get_all_cached_models,
    is_running, is_done, get_job, start_scoring,
)
from ui.styles import inject_css
from ui.cards import (
    show_top10_cards, show_score_table, show_candidate_table,
    show_consensus, show_progress,
)


# ══════════════════════════════════════════════════════════════════════════════
# CSS + Header
# ══════════════════════════════════════════════════════════════════════════════

inject_css()

# Token 计数显示
usage = get_token_usage()
if usage["total"] > 0:
    total = usage["total"]
    display = f"{total / 10000:.1f}万" if total >= 10000 else f"{total:,}"
    st.markdown(f"""<div style="
        position:fixed; top:10px; right:18px; z-index:9999;
        background:rgba(99,102,241,0.9); color:#fff;
        border-radius:50px; padding:4px 14px;
        font-size:0.75rem; font-weight:700;
        box-shadow:0 2px 8px rgba(0,0,0,0.15);
    ">🔢 Token: {display}</div>""", unsafe_allow_html=True)

st.markdown("""<div class="app-header">
  <h1>🏆 每日 Top 10 精选</h1>
  <p>人气榜 + 成交额榜 → Tushare 数据增强 → AI 深度分析 → 精选 Top 10</p>
  <p style="font-weight:700; color:#fff;">立花道雪</p>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### ⚙️ 设置")
    model_name = st.selectbox("AI 模型", MODEL_NAMES, index=2,
                              help="选择用于深度分析的 AI 模型")
    cfg = MODEL_CONFIGS.get(model_name, {})
    st.caption(f"📌 {cfg.get('note', '')}")

    top_n = st.slider("候选池大小", 30, 100, 50, step=10,
                       help="从人气榜和成交额榜各取 Top N")
    max_analyze = st.slider("最大分析数量", 10, 50, 30, step=5,
                             help="初筛后最多分析多少只股票（控制 Token 消耗）")

    st.markdown("---")
    st.markdown("### 📊 数据来源")
    st.caption("🔥 东方财富人气榜")
    st.caption("💰 东方财富成交额榜")
    try:
        from data.tushare_data import get_ts_status
        st.caption(f"📈 {get_ts_status()}")
    except Exception:
        st.caption("📈 Tushare 未加载")

    st.markdown("---")
    # 邮件推送
    st.markdown("### 📧 邮件推送")
    try:
        from utils.email_sender import smtp_configured
        if smtp_configured():
            email_addr = st.text_input("收件邮箱", value="", placeholder="your@email.com",
                                       key="email_input")
            st.caption("分析完成后可一键推送报告到邮箱")
        else:
            st.caption("⚠️ SMTP 未配置")
            st.caption("请在 Secrets 中添加：")
            st.code("SMTP_HOST\nSMTP_PORT\nSMTP_USER\nSMTP_PASS", language=None)
            email_addr = ""
    except Exception:
        st.caption("📧 邮件模块未加载")
        email_addr = ""

    st.markdown("---")
    if st.button("🔄 重置 Token 计数"):
        reset_token_usage()
        st.rerun()

    st.markdown("""<div class="disclaimer">
    ⚠️ 本工具仅供学习研究，不构成投资建议。股市有风险，投资需谨慎。
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════════════

# Step 1: 获取数据
st.markdown("### 📡 数据获取")

col1, col2 = st.columns(2)

with col1:
    with st.spinner("加载人气榜..."):
        hot_df, hot_err = get_hot_rank(top_n)
    if hot_err:
        st.warning(f"人气榜：{hot_err}")
    else:
        st.success(f"🔥 人气榜 Top {len(hot_df)}")

with col2:
    with st.spinner("加载成交额榜..."):
        vol_df, vol_err = get_volume_rank(top_n)
    if vol_err:
        st.warning(f"成交额榜：{vol_err}")
    else:
        st.success(f"💰 成交额榜 Top {len(vol_df)}")

# 板块轮动信号
try:
    from data.tushare_data import get_sector_rotation
    sectors = get_sector_rotation()
    if sectors.get("概念板块") or sectors.get("行业板块"):
        with st.expander("📊 今日板块轮动", expanded=False):
            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown("**🔥 概念板块 Top5**")
                for s in sectors.get("概念板块", []):
                    st.caption(s)
            with sc2:
                st.markdown("**🏭 行业板块 Top5**")
                for s in sectors.get("行业板块", []):
                    st.caption(s)
except Exception:
    pass

# Step 2: 合并 + 初筛
merged = merge_candidates(hot_df, vol_df)

before_count = len(merged)
filtered = apply_filters(merged)
after_count = len(filtered)

if before_count > 0:
    st.caption(get_filter_summary(before_count, after_count))

# 限制分析数量
candidates = filtered.head(max_analyze)

# Step 3: 展示候选池（带来源着色）
with st.expander(f"📋 候选池（{len(candidates)} 只）", expanded=False):
    show_candidate_table(candidates)

st.markdown("---")

# Step 4: AI 分析
st.markdown("### 🤖 AI 深度分析")


def _show_results(result_df, summary_text=""):
    """展示分析结果 + 导出 + 邮件"""
    show_top10_cards(result_df)

    # 导出 + 完整评分表
    col_export, col_table = st.columns([1, 1])
    with col_export:
        # CSV 导出按钮
        csv_cols = [c for c in ["代码", "股票名称", "行业", "最新价", "涨跌幅",
                                 "基本面", "题材热度", "技术面", "综合评分",
                                 "短线建议", "模型"]
                    if c in result_df.columns]
        csv_data = result_df[csv_cols].to_csv(index=True, encoding="utf-8-sig")
        from datetime import date as _date
        st.download_button(
            "📥 导出 CSV",
            csv_data,
            file_name=f"top10_{_date.today().isoformat()}.csv",
            mime="text/csv",
        )
    with col_table:
        if email_addr:
            if st.button("📧 发送报告到邮箱", key="send_email"):
                with st.spinner("正在发送..."):
                    from utils.email_sender import send_report_email
                    ok, msg = send_report_email(email_addr, result_df,
                                                summary_text, model_name)
                    if ok:
                        st.success(f"✅ 已发送至 {email_addr}")
                    else:
                        st.error(msg)

    with st.expander("📊 完整评分表", expanded=False):
        show_score_table(result_df)

    if summary_text:
        st.markdown("---")
        st.markdown("### 📝 每日总结报告")
        st.markdown(summary_text)

    # 多模型共识分析
    cached_models = get_all_cached_models()
    if len(cached_models) >= 2:
        st.markdown("---")
        st.markdown("### 🤝 多模型共识分析")
        cached_results = {}
        for m in cached_models:
            # 找到对应的 display name
            for display_name in MODEL_NAMES:
                if m in display_name or display_name.split("·")[-1].strip() in m:
                    r = get_cached_result(display_name)
                    if r is not None and not r.empty:
                        cached_results[display_name] = r
                    break
            else:
                r = get_cached_result(m)
                if r is not None and not r.empty:
                    cached_results[m] = r
        if len(cached_results) >= 2:
            show_consensus(cached_results)
        else:
            st.info(f"今日已有 {len(cached_models)} 个模型的缓存，切换模型查看共识")


# 检查缓存
cached = get_cached_result(model_name)
cached_summary = get_cached_summary(model_name) or ""

if cached is not None and not cached.empty:
    st.success(f"📦 已有今日 {model_name} 的分析缓存（{len(cached)} 只），直接展示结果")
    _show_results(cached, cached_summary)
    if st.button("🔄 重新分析（忽略缓存）", key="re_analyze"):
        from datetime import date as _date
        st.session_state.pop(f"top10_result_{_date.today().isoformat()}_{model_name}", None)
        st.session_state.pop(f"top10_summary_{_date.today().isoformat()}_{model_name}", None)
        st.session_state.pop("bg_job", None)
        st.rerun()

elif is_running(st.session_state):
    show_progress(get_job(st.session_state))
    time.sleep(2)
    st.rerun()

elif is_done(st.session_state):
    job = get_job(st.session_state)
    if job.get("error"):
        st.error(f"分析失败：{job['error']}")
        if st.button("🔄 重试"):
            st.session_state.pop("bg_job", None)
            st.rerun()
    elif job.get("result") is not None:
        _show_results(job["result"], job.get("summary", ""))

else:
    if candidates.empty:
        st.warning("候选池为空，请检查数据源")
    else:
        st.info(f"将使用 **{model_name}** 对 {len(candidates)} 只候选股进行深度分析"
                f"（3路并发，预计耗时约 {len(candidates) * 8 // 3} 秒）")
        if st.button("🚀 开始 AI 分析", type="primary", key="start_analysis"):
            start_scoring(st.session_state, candidates, model_name)
            time.sleep(0.5)
            st.rerun()
