"""Prompt 模板 — Top10 选股分析"""


SYSTEM_SCORER = (
    "你是一位顶级A股短线投资顾问，擅长从基本面、题材热度、技术面三个维度筛选优质标的。"
    "你的分析风格：数据驱动、逻辑清晰、敢于给出明确评分和结论。"
    "评分标准偏好：基本面扎实 + 题材正宗（不是蹭概念）+ 短期有明显启动趋势（放量突破、均线多头等）。"
    "重要：下方提供的行情数据和K线数据是准确的实时数据，请以此为基础分析。"
    "对于近期新闻、公告等信息，请结合联网搜索结果判断。"
)


def build_score_prompt(stock_code: str, stock_name: str,
                       price: float, change_pct: float,
                       hot_rank: int | None = None,
                       vol_rank: int | None = None,
                       volume_yi: float | None = None,
                       turnover_rate: float | None = None,
                       volume_ratio: float | None = None,
                       net_flow_wan: float | None = None,
                       pe: float | None = None,
                       pb: float | None = None,
                       mkt_cap_yi: float | None = None,
                       industry: str | None = None,
                       kline_summary: str | None = None) -> str:
    """构建单只股票的评分 prompt"""

    rank_info = []
    if hot_rank is not None:
        rank_info.append(f"人气排名第{hot_rank}")
    if vol_rank is not None:
        rank_info.append(f"成交额排名第{vol_rank}")
    rank_str = "、".join(rank_info) if rank_info else "无排名信息"

    # 基础行情
    data_lines = [f"最新价：{price}元，涨跌幅：{change_pct}%"]
    if industry:
        data_lines.append(f"所属行业：{industry}")
    if volume_yi:
        data_lines.append(f"成交额：{volume_yi}亿元")
    if turnover_rate:
        data_lines.append(f"换手率：{turnover_rate}%")
    if volume_ratio:
        data_lines.append(f"量比：{volume_ratio}")
    if pe and pe > 0:
        data_lines.append(f"市盈率(PE_TTM)：{pe:.1f}")
    if pb and pb > 0:
        data_lines.append(f"市净率(PB)：{pb:.2f}")
    if mkt_cap_yi and mkt_cap_yi > 0:
        data_lines.append(f"总市值：{mkt_cap_yi:.0f}亿元")
    if net_flow_wan is not None:
        flow_desc = f"+{net_flow_wan}" if net_flow_wan >= 0 else f"{net_flow_wan}"
        data_lines.append(f"今日主力净流入：{flow_desc}万元")

    data_block = "\n- ".join(data_lines)

    # K线技术面数据
    kline_block = ""
    if kline_summary:
        kline_block = f"""

## K线技术面数据（真实数据）
{kline_summary}
"""

    return f"""请对以下A股标的进行深度分析和评分：

## 股票信息
- 股票：{stock_name}（{stock_code}）
- 今日排名：{rank_str}

## 实时行情数据
- {data_block}
{kline_block}
## 请从以下三个维度分析并评分（每项1-10分）：

### 1. 基本面（权重35%）
- 公司主营业务及行业地位（行业：{industry or '请搜索确认'}）
- 近期业绩表现（请搜索最新财报/业绩预告）
- 估值水平（参考上方PE={pe or "N/A"}, PB={pb or "N/A"}，结合行业均值）
- 财务健康度

### 2. 题材热度（权重35%）
- 所属概念板块及题材正宗程度（是主业还是蹭概念）
- 当前市场对该题材的关注度和持续性
- 是否有近期催化剂（请搜索最新政策/事件/公告）
- 题材的想象空间和天花板

### 3. 技术面/短线动能（权重30%）
- 量价配合（换手率{turnover_rate or "N/A"}%，量比{volume_ratio or "N/A"}）
- 主力资金流向（今日净流入{net_flow_wan or "N/A"}万）
- K线形态与均线系统（参考上方K线数据）
- 短线支撑位和压力位

## 输出格式要求（严格按此格式）：

**综合评分：X.X/10**

| 维度 | 评分 | 关键依据 |
|------|------|----------|
| 基本面 | X/10 | 一句话总结 |
| 题材热度 | X/10 | 一句话总结 |
| 技术面 | X/10 | 一句话总结 |

**核心逻辑：**（2-3句话说明为什么值得/不值得关注）

**风险提示：**（1-2个主要风险点）

**短线建议：**（明确给出：强烈推荐/推荐/观望/回避）"""


SYSTEM_SUMMARY = (
    "你是一位资深A股投资策略师，正在为客户撰写每日精选股票报告。"
    "报告要求：专业但易懂，重点突出，结论明确。"
)


def build_summary_prompt(top_stocks_text: str, total_candidates: int) -> str:
    """构建 Top10 汇总报告的 prompt"""
    return f"""以下是今日从{total_candidates}只热门候选股中，经AI深度分析后筛选出的Top 10推荐标的及其分析摘要：

{top_stocks_text}

请撰写一份简洁的【今日Top10精选报告】，包含：

1. **市场概览**（2-3句话概括今日热门股票的整体特征和市场情绪）

2. **Top 10 精选理由总结**（用表格呈现）：
| 排名 | 股票 | 综合评分 | 一句话推荐理由 |
|------|------|----------|----------------|

3. **今日主线题材**（总结Top10中出现的主要投资主线，1-2个）

4. **风险提醒**（整体市场风险或需要注意的共性风险）

注意：这是投资参考，不构成投资建议。请在报告末尾加上免责声明。"""
