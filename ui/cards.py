"""Top 10 结果展示卡片"""

import pandas as pd
import streamlit as st


def show_top10_cards(df: pd.DataFrame):
    """展示 Top 10 推荐股票卡片"""
    if df.empty:
        st.info("暂无推荐结果")
        return

    top = df.head(10)
    st.markdown("### 🏆 今日 Top 10 精选")

    for i, (_, row) in enumerate(top.iterrows(), 1):
        score = row.get("综合评分", 0)
        name = row.get("股票名称", "")
        code = row.get("代码", "")
        price = row.get("最新价", 0)
        change = row.get("涨跌幅", 0)
        model = row.get("模型", "")

        # 颜色
        if score >= 8:
            border_color = "#22c55e"
            badge_bg = "#f0fdf4"
            badge_color = "#16a34a"
        elif score >= 6:
            border_color = "#6366f1"
            badge_bg = "#eef2ff"
            badge_color = "#6366f1"
        else:
            border_color = "#f97316"
            badge_bg = "#fff7ed"
            badge_color = "#c2410c"

        import math
        _change_safe = change if (isinstance(change, float) and not math.isnan(change)) else 0.0
        change_color = "#22c55e" if _change_safe >= 0 else "#ef4444"
        change_sign = "+" if _change_safe >= 0 else ""
        price_str = f"{price:.2f}" if isinstance(price, float) and not math.isnan(price) else str(price)
        change_str = f"{change_sign}{_change_safe:.2f}"

        st.markdown(f"""<div style="
            background: #fff;
            border: 2px solid {border_color};
            border-radius: 16px;
            padding: 1.2rem 1.5rem;
            margin: 0.6rem 0;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        ">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
                <div>
                    <span style="font-size:1.4rem; font-weight:800; color:#1e1b4b;">
                        #{i} {name}
                    </span>
                    <span style="font-size:0.85rem; color:#6b7280; margin-left:8px;">{code}</span>
                </div>
                <div style="
                    background:{badge_bg}; color:{badge_color};
                    border-radius:50px; padding:4px 16px;
                    font-weight:800; font-size:1.1rem;
                ">{score}/10</div>
            </div>
            <div style="display:flex; gap:20px; font-size:0.88rem; color:#6b7280;">
                <span>💰 {price_str}元</span>
                <span style="color:{change_color}; font-weight:600;">{change_str}%</span>
                <span>🤖 {model}</span>
            </div>
        </div>""", unsafe_allow_html=True)

        # 展开查看详细分析
        analysis = row.get("AI分析", "")
        if analysis and not analysis.startswith("分析失败"):
            with st.expander(f"📋 查看 {name} 详细分析", expanded=False):
                st.markdown(analysis)


def show_score_table(df: pd.DataFrame):
    """展示评分总表"""
    if df.empty:
        return

    display_cols = ["代码", "股票名称", "最新价", "涨跌幅", "综合评分", "模型"]
    available = [c for c in display_cols if c in df.columns]
    display = df[available].copy()

    if "涨跌幅" in display.columns:
        display["涨跌幅"] = display["涨跌幅"].apply(
            lambda x: (f"+{x:.2f}%" if x >= 0 else f"{x:.2f}%")
            if pd.notna(x) else "N/A"
        )
    if "综合评分" in display.columns:
        display["综合评分"] = display["综合评分"].apply(
            lambda x: f"{x:.1f}/10" if pd.notna(x) else "N/A"
        )

    st.dataframe(display, use_container_width=True, hide_index=False)


def show_progress(job: dict):
    """显示后台任务进度"""
    if not job:
        return

    status = job.get("status", "")
    progress = job.get("progress", [])
    current = job.get("current", 0)
    total = job.get("total", 1)

    if status == "running":
        pct = current / total if total > 0 else 0
        st.progress(pct, text=f"分析进度：{current}/{total}")
        with st.status("🔍 AI 正在逐只深度分析...", expanded=True, state="running"):
            for msg in progress[-8:]:  # 只显示最近8条
                st.write(msg)
    elif status == "done" and job.get("error"):
        st.error(f"分析失败：{job['error']}")
    elif status == "done":
        st.success(f"✅ 分析完成！共评分 {total} 只股票")
