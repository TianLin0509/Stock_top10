"""Top 10 结果展示卡片"""

import math
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
        advice = row.get("短线建议", "")
        industry = row.get("行业", "")
        s_fund = row.get("基本面")
        s_theme = row.get("题材热度")
        s_tech = row.get("技术面")

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

        _change_safe = change if (isinstance(change, float) and not math.isnan(change)) else 0.0
        change_color = "#22c55e" if _change_safe >= 0 else "#ef4444"
        change_sign = "+" if _change_safe >= 0 else ""
        price_str = f"{price:.2f}" if isinstance(price, (int, float)) and not (isinstance(price, float) and math.isnan(price)) else str(price)
        change_str = f"{change_sign}{_change_safe:.2f}"

        # 短线建议标签
        advice_map = {
            "强烈推荐": ("#dc2626", "#fef2f2", "🔥 强烈推荐"),
            "推荐": ("#16a34a", "#f0fdf4", "👍 推荐"),
            "观望": ("#d97706", "#fffbeb", "👀 观望"),
            "回避": ("#6b7280", "#f3f4f6", "⛔ 回避"),
        }
        adv_color, adv_bg, adv_text = advice_map.get(advice, ("#6b7280", "#f3f4f6", ""))
        advice_html = f"""<span style="
            background:{adv_bg}; color:{adv_color};
            border-radius:50px; padding:2px 10px;
            font-weight:700; font-size:0.78rem; margin-left:10px;
        ">{adv_text}</span>""" if adv_text else ""

        # 行业标签
        industry_html = f"""<span style="
            background:#f0f9ff; color:#0369a1;
            border-radius:50px; padding:2px 8px;
            font-size:0.72rem; margin-left:6px;
        ">{industry}</span>""" if industry else ""

        # 子评分进度条
        def _bar(label, val, color):
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return ""
            pct = min(val * 10, 100)
            return f"""<div style="display:flex; align-items:center; gap:6px; margin-top:2px;">
                <span style="font-size:0.75rem; color:#6b7280; min-width:56px;">{label}</span>
                <div style="flex:1; background:#f1f5f9; border-radius:4px; height:8px; overflow:hidden;">
                    <div style="width:{pct}%; background:{color}; height:100%; border-radius:4px;"></div>
                </div>
                <span style="font-size:0.75rem; color:#374151; min-width:28px; text-align:right;">{val:.0f}</span>
            </div>"""

        sub_bars = _bar("基本面", s_fund, "#3b82f6") + _bar("题材", s_theme, "#f59e0b") + _bar("技术面", s_tech, "#22c55e")

        # 量化预评分标签
        quant_total = row.get("量化总分")
        quant_signal = row.get("量化信号", "")
        quant_html = ""
        if quant_total and not (isinstance(quant_total, float) and math.isnan(quant_total)):
            q_color = "#16a34a" if quant_total >= 65 else "#f59e0b" if quant_total >= 50 else "#ef4444"
            quant_html = f"""<div style="margin-top:6px; display:flex; align-items:center; gap:8px;">
                <span style="font-size:0.72rem; color:#6b7280;">量化预评分</span>
                <span style="background:{q_color}15; color:{q_color}; border-radius:4px;
                    padding:1px 8px; font-size:0.72rem; font-weight:700;">{int(quant_total)}/100 {quant_signal}</span>
            </div>"""

        sub_section = f'<div style="margin-top:8px;">{sub_bars}{quant_html}</div>' if (sub_bars or quant_html) else ""

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
                    {industry_html}
                    {advice_html}
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
            {sub_section}
        </div>""", unsafe_allow_html=True)

        # 展开查看详细分析 + K线图
        analysis = row.get("AI分析", "")
        if analysis and not analysis.startswith("分析失败"):
            with st.expander(f"📋 查看 {name} 详细分析", expanded=False):
                st.markdown(analysis)
                # K线图
                _show_kline_chart(code, name)


def _show_kline_chart(code: str, name: str):
    """在详细分析中展示 K 线图"""
    try:
        from data.tushare_data import to_ts_code, _pro, _retry, _ndays_ago, _today
        if not _pro:
            return
        ts_code = to_ts_code(code)
        df = _retry(lambda: _pro.daily(
            ts_code=ts_code,
            start_date=_ndays_ago(60),
            end_date=_today()
        ))
        if df is None or df.empty:
            return
        df = df.sort_values("trade_date").reset_index(drop=True)

        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                            row_heights=[0.7, 0.3],
                            vertical_spacing=0.02)

        # K线
        fig.add_trace(go.Candlestick(
            x=df["trade_date"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="K线",
            increasing_line_color="#ef4444", decreasing_line_color="#22c55e",
            increasing_fillcolor="#ef4444", decreasing_fillcolor="#22c55e",
        ), row=1, col=1)

        # 均线
        for period, color in [(5, "#f59e0b"), (20, "#3b82f6"), (60, "#8b5cf6")]:
            ma = df["close"].rolling(period).mean()
            fig.add_trace(go.Scatter(
                x=df["trade_date"], y=ma, name=f"MA{period}",
                line=dict(color=color, width=1),
            ), row=1, col=1)

        # 成交量
        colors = ["#ef4444" if c >= o else "#22c55e"
                  for c, o in zip(df["close"], df["open"])]
        fig.add_trace(go.Bar(
            x=df["trade_date"], y=df["vol"], name="成交量",
            marker_color=colors, opacity=0.6,
        ), row=2, col=1)

        fig.update_layout(
            height=360, margin=dict(l=0, r=0, t=30, b=0),
            xaxis_rangeslider_visible=False,
            showlegend=False,
            title=dict(text=f"{name} 近60日K线", font=dict(size=13)),
        )
        fig.update_xaxes(type="category", tickangle=-45, nticks=10)

        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass  # K线图加载失败不影响其他功能


def show_score_table(df: pd.DataFrame):
    """展示评分总表"""
    if df.empty:
        return

    display_cols = ["代码", "股票名称", "行业", "最新价", "涨跌幅",
                    "基本面", "题材热度", "技术面", "综合评分", "短线建议", "模型"]
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


def show_candidate_table(df: pd.DataFrame):
    """带来源着色的候选池展示"""
    if df.empty:
        st.warning("候选池为空")
        return

    display_cols = [c for c in ["代码", "股票名称", "最新价", "涨跌幅", "来源",
                                 "人气排名", "成交额排名", "成交额(亿)",
                                 "换手率", "量比", "市盈率", "总市值(亿)",
                                 "主力净流入(万)"]
                    if c in df.columns]
    display = df[display_cols].copy()

    # 排名列转整数
    for col in ["人气排名", "成交额排名"]:
        if col in display.columns:
            display[col] = display[col].apply(
                lambda x: int(x) if pd.notna(x) else ""
            )

    # 所有浮点列最多保留两位小数
    for col in ["最新价", "涨跌幅", "成交额(亿)", "换手率", "量比",
                "市盈率", "总市值(亿)", "主力净流入(万)"]:
        if col in display.columns:
            display[col] = display[col].apply(
                lambda x: round(x, 2) if isinstance(x, float) and pd.notna(x) else x
            )

    # 来源着色
    if "来源" in display.columns:
        def _style_source(val):
            colors = {"双榜": "background-color: #dcfce7; color: #166534",
                      "人气榜": "background-color: #dbeafe; color: #1e40af",
                      "成交额榜": "background-color: #fff7ed; color: #9a3412"}
            return colors.get(val, "")

        styled = display.style.map(_style_source, subset=["来源"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.dataframe(display, use_container_width=True, hide_index=True)


def show_consensus(cached_results: dict):
    """多模型共识分析"""
    if len(cached_results) < 2:
        st.info("需要至少2个模型的分析结果才能进行共识分析。请切换模型后再次运行分析。")
        return

    # 收集每个模型的 Top10 股票代码
    model_picks = {}
    for model, df in cached_results.items():
        top10 = df.head(10)
        model_picks[model] = set(top10["代码"].tolist())

    # 找出共识股票（出现在2个以上模型的 Top10 中）
    all_codes = {}
    for model, codes in model_picks.items():
        for code in codes:
            if code not in all_codes:
                all_codes[code] = []
            all_codes[code].append(model)

    consensus = {code: models for code, models in all_codes.items() if len(models) >= 2}

    if not consensus:
        st.warning("各模型的 Top10 没有重叠，暂无共识股票")
        return

    st.markdown(f"**共 {len(consensus)} 只共识股票**（出现在 2+ 模型的 Top10 中）")

    # 构建共识表
    rows = []
    for code, models in sorted(consensus.items(), key=lambda x: -len(x[1])):
        # 取各模型的评分
        scores = {}
        name = ""
        for model, df in cached_results.items():
            match = df[df["代码"] == code]
            if not match.empty:
                r = match.iloc[0]
                name = r.get("股票名称", "")
                scores[model] = r.get("综合评分", 0)
        avg_score = sum(scores.values()) / len(scores) if scores else 0
        rows.append({
            "代码": code,
            "股票名称": name,
            "入选模型数": len(models),
            "平均评分": round(avg_score, 1),
            "入选模型": " / ".join([m.split("·")[0].strip() for m in models]),
        })

    consensus_df = pd.DataFrame(rows).sort_values(
        ["入选模型数", "平均评分"], ascending=[False, False]
    ).reset_index(drop=True)
    consensus_df.index = consensus_df.index + 1

    st.dataframe(consensus_df, use_container_width=True, hide_index=False)


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
        with st.status("🔍 AI 正在深度分析...", expanded=True, state="running"):
            for msg in progress[-8:]:
                st.write(msg)
    elif status == "done" and job.get("error"):
        st.error(f"分析失败：{job['error']}")
    elif status == "done":
        st.success(f"✅ 分析完成！共评分 {total} 只股票")
