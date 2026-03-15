"""🏆 每日 Top10 精选 — AI驱动 · 每日自动分析"""

import streamlit as st
import time as _time
from datetime import date

st.set_page_config(
    page_title="每日 Top10 精选",
    page_icon="🏆",
    layout="wide",
)

# ── 启动定时调度器 ──
from utils.scheduler import start_top10_scheduler
start_top10_scheduler()

# ── 导入模块 ──
from config import MODEL_CONFIGS, MODEL_NAMES, DEFAULT_MODEL, ADMIN_USERNAME
from core.ai_client import get_token_usage
from top10.runner import (
    get_cached_result, get_cached_summary, get_cached_meta,
    get_all_cached_models, start_scoring, is_running, get_job,
)
from top10.deep_runner import (
    start_deep_top10_async, get_deep_status, is_deep_running,
)
from top10.cards import show_top10_cards, show_progress


# ══════════════════════════════════════════════════════════════════════════════
# 侧边栏
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🏆 每日 Top10 精选")
    st.caption("AI驱动 · 每日自动分析")
    st.divider()

    # 模型选择
    cached_models = get_all_cached_models()
    if cached_models:
        st.success(f"✅ 今日已有 **{len(cached_models)}** 个模型结果")

    selected_model = st.selectbox(
        "选择查看模型",
        MODEL_NAMES,
        index=MODEL_NAMES.index(DEFAULT_MODEL) if DEFAULT_MODEL in MODEL_NAMES else 0,
        help="选择要查看的模型结果",
    )

    # 管理员区域
    st.divider()
    st.markdown("#### 🔐 管理员操作")

    admin_pass = st.text_input("管理员密码", type="password", key="admin_pass")
    is_admin = admin_pass == st.secrets.get("ADMIN_PASS", "")

    if is_admin:
        st.success("✅ 管理员已验证")

        trigger_model = st.selectbox(
            "分析模型",
            MODEL_NAMES,
            index=MODEL_NAMES.index(DEFAULT_MODEL) if DEFAULT_MODEL in MODEL_NAMES else 0,
            key="trigger_model",
        )
        candidate_count = st.slider("候选池数量", 30, 200, 100, 10, key="candidate_count")

        # 深度分析状态
        deep_status_sidebar = get_deep_status()
        if deep_status_sidebar and deep_status_sidebar.get("status") == "running":
            st.warning(f"⏳ 深度分析进行中... ({deep_status_sidebar.get('phase', '')})")
        elif is_deep_running():
            st.warning("⏳ 深度分析进行中...")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 快速分析", use_container_width=True,
                         help="仅AI三维评分，不含深度分析"):
                from top10.hot_rank import get_hot_rank, get_volume_rank, merge_candidates
                from top10.stock_filter import apply_filters

                with st.spinner("获取候选池..."):
                    hot_df, _ = get_hot_rank(candidate_count)
                    vol_df, _ = get_volume_rank(candidate_count)
                    merged = merge_candidates(hot_df, vol_df)
                    filtered = apply_filters(merged)
                    candidates = filtered.head(candidate_count)

                if candidates.empty:
                    st.error("候选池为空，请稍后重试")
                else:
                    st.info(f"候选池: {len(candidates)} 只，开始评分...")
                    start_scoring(st.session_state, candidates, trigger_model,
                                  username=ADMIN_USERNAME)

        with col2:
            if st.button("🔬 深度分析", use_container_width=True,
                         help="完整6阶段深度分析流水线",
                         disabled=is_deep_running()):
                started = start_deep_top10_async(
                    model_name=trigger_model,
                    candidate_count=candidate_count,
                    username=ADMIN_USERNAME,
                )
                if started:
                    st.success("🚀 深度分析已启动！")
                else:
                    st.warning("已有分析在运行中")

    elif admin_pass:
        st.error("❌ 密码错误")

    # Token 统计
    st.divider()
    tokens = get_token_usage()
    total = tokens["total"]
    if total >= 10000:
        st.caption(f"Token: {total / 10000:.1f}万")
    elif total > 0:
        st.caption(f"Token: {total:,}")

    st.markdown(
        '<div style="text-align:center;color:#9ca3af;font-size:0.75rem;margin-top:20px;">'
        'by 立花道雪</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 主区域
# ══════════════════════════════════════════════════════════════════════════════

# 显示后台任务进度
job = get_job(st.session_state)
if is_running(st.session_state):
    show_progress(job)
    _time.sleep(3)
    st.rerun()
elif job.get("status") == "done":
    if job.get("error"):
        st.error(f"分析失败：{job['error']}")
    elif job.get("result") is not None:
        show_progress(job)

# 显示深度分析进度
deep_status = get_deep_status()
if deep_status and deep_status.get("status") == "running":
    phase = deep_status.get("phase", "")
    progress = deep_status.get("progress", [])
    st.info(f"🔬 深度分析进行中: {phase}")
    if progress:
        with st.expander("查看进度详情", expanded=False):
            for msg in progress[-10:]:
                st.write(msg)
    _time.sleep(5)
    st.rerun()

# 尝试读取缓存结果
cached_df = get_cached_result(selected_model)

if cached_df is not None and not cached_df.empty:
    # 显示元信息
    meta = get_cached_meta(selected_model)
    if meta:
        tokens_used = meta.get("tokens", 0)
        triggered_by = meta.get("user", "")
        if tokens_used >= 10000:
            tokens_str = f"{tokens_used / 10000:.1f}万"
        else:
            tokens_str = f"{tokens_used:,}"
        st.caption(
            f"📊 {date.today().strftime('%Y-%m-%d')} | 模型: {selected_model} | "
            f"触发: {triggered_by} | Token: {tokens_str}"
        )

    # 显示总结
    summary = get_cached_summary(selected_model)
    if summary:
        with st.expander("📝 每日总结", expanded=False):
            st.markdown(summary)

    # 三Tab 卡片展示
    show_top10_cards(cached_df)

    # 深度分析展示（如果用户点击了某只股票）
    pick_code = st.session_state.get("_top10_pick")
    if pick_code:
        st.divider()
        pick_row = cached_df[cached_df["代码"] == pick_code]
        if not pick_row.empty:
            pick_name = pick_row.iloc[0]["股票名称"]
            st.subheader(f"🔍 {pick_name}（{pick_code}）深度分析")

            ai_text = pick_row.iloc[0].get("AI分析", "")
            if ai_text:
                st.markdown(ai_text)

        if st.button("← 返回 Top10 列表"):
            del st.session_state["_top10_pick"]
            st.rerun()

else:
    # 无结果 — 显示欢迎页
    st.markdown(
        '<div style="text-align:center;padding:60px 20px;">'
        '<h2 style="color:#6366f1;">🏆 每日 Top10 精选</h2>'
        '<p style="color:#6b7280;font-size:1.1rem;">'
        'AI驱动的A股每日热门股票精选<br>'
        '每晚 22:00 自动分析 · 管理员可手动触发'
        '</p>'
        '<p style="color:#9ca3af;margin-top:20px;">'
        '今日暂无分析结果，请等待自动分析或由管理员手动触发'
        '</p></div>',
        unsafe_allow_html=True,
    )
