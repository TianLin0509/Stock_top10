"""Stock Top 10 — 每日人气+成交额 Top 100 → AI 精选 Top 10"""

import time
import streamlit as st

st.set_page_config(
    page_title="每日 Top10 精选",
    page_icon="🏆",
    layout="wide",
)

from config import MODEL_CONFIGS, MODEL_NAMES
from ai.client import get_ai_client, get_token_usage, reset_token_usage
from data.hot_rank import get_hot_rank, get_volume_rank, merge_candidates
from data.stock_filter import apply_filters, get_filter_summary
from analysis.runner import (
    get_cached_result, is_running, is_done, get_job, start_scoring,
)
from ui.styles import inject_css
from ui.cards import show_top10_cards, show_score_table, show_progress


# ══════════════════════════════════════════════════════════════════════════════
# CSS + Header
# ══════════════════════════════════════════════════════════════════════════════

inject_css()

# Token 计数显示
usage = get_token_usage()
if usage["total"] > 0:
    st.markdown(f"""<div style="
        position:fixed; top:10px; right:18px; z-index:9999;
        background:rgba(99,102,241,0.9); color:#fff;
        border-radius:50px; padding:4px 14px;
        font-size:0.75rem; font-weight:700;
        box-shadow:0 2px 8px rgba(0,0,0,0.15);
    ">🔢 Token: {usage['total']:,}</div>""", unsafe_allow_html=True)

st.markdown("""<div class="app-header">
  <h1>🏆 每日 Top 10 精选</h1>
  <p>人气榜 + 成交额榜 → 量化初筛 → AI 深度分析 → 精选 Top 10</p>
  <p style="font-weight:700; color:#fff;">立花道雪</p>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# Sidebar — 模型选择 + 参数
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

# Step 2: 合并 + 初筛
merged = merge_candidates(hot_df, vol_df)

before_count = len(merged)
filtered = apply_filters(merged)
after_count = len(filtered)

if before_count > 0:
    st.caption(get_filter_summary(before_count, after_count))

# 限制分析数量
candidates = filtered.head(max_analyze)

# Step 3: 展示候选池
with st.expander(f"📋 候选池（{len(candidates)} 只）", expanded=False):
    if not candidates.empty:
        display_cols = [c for c in ["代码", "股票名称", "最新价", "涨跌幅", "来源",
                                     "人气排名", "成交额排名", "成交额(亿)",
                                     "换手率", "量比", "主力净流入(万)"]
                        if c in candidates.columns]
        st.dataframe(candidates[display_cols], use_container_width=True, hide_index=True)
    else:
        st.warning("候选池为空，无法进行分析")

st.markdown("---")

# Step 4: AI 分析
st.markdown("### 🤖 AI 深度分析")

# 检查缓存
cached = get_cached_result(model_name)

if cached is not None and not cached.empty:
    st.success(f"📦 已有今日 {model_name} 的分析缓存（{len(cached)} 只），直接展示结果")
    show_top10_cards(cached)
    with st.expander("📊 完整评分表", expanded=False):
        show_score_table(cached)
    if st.button("🔄 重新分析（忽略缓存）", key="re_analyze"):
        st.session_state.pop(f"top10_result_{__import__('datetime').date.today().isoformat()}_{model_name}", None)
        st.session_state.pop("bg_job", None)
        st.rerun()

elif is_running(st.session_state):
    # 显示进度
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
        result_df = job["result"]
        show_top10_cards(result_df)
        with st.expander("📊 完整评分表", expanded=False):
            show_score_table(result_df)
        # 每日总结报告
        summary = job.get("summary", "")
        if summary:
            st.markdown("---")
            st.markdown("### 📝 每日总结报告")
            st.markdown(summary)

else:
    # 未开始
    if candidates.empty:
        st.warning("候选池为空，请检查数据源")
    else:
        st.info(f"将使用 **{model_name}** 对 {len(candidates)} 只候选股进行深度分析")
        if st.button("🚀 开始 AI 分析", type="primary", key="start_analysis"):
            start_scoring(st.session_state, candidates, model_name)
            time.sleep(0.5)
            st.rerun()
