"""Prompt 模板 — Top10 选股分析"""


SYSTEM_SCORER = (
    "你是一位顶级A股短线投资顾问，擅长从基本面、题材热度、技术面三个维度筛选优质标的。"
    "你的分析风格：数据驱动、逻辑清晰、敢于给出明确评分和结论。"
    "评分标准偏好：基本面扎实 + 题材正宗（不是蹭概念）+ 短期有明显启动趋势（放量突破、均线多头等）。"
)


def build_score_prompt(stock_code: str, stock_name: str,
                       price: float, change_pct: float,
                       hot_rank: int | None = None,
                       vol_rank: int | None = None,
                       volume_yi: float | None = None) -> str:
    """构建单只股票的评分 prompt"""

    rank_info = []
    if hot_rank is not None:
        rank_info.append(f"人气排名第{hot_rank}")
    if vol_rank is not None:
        rank_info.append(f"成交额排名第{vol_rank}")
    rank_str = "、".join(rank_info) if rank_info else "无排名信息"

    vol_str = f"，成交额约{volume_yi}亿" if volume_yi else ""

    return f"""请对以下A股标的进行深度分析和评分：

## 股票信息
- 股票：{stock_name}（{stock_code}）
- 最新价：{price}元，涨跌幅：{change_pct}%{vol_str}
- 今日排名：{rank_str}

## 请从以下三个维度分析并评分（每项1-10分）：

### 1. 基本面（权重35%）
- 公司主营业务及行业地位
- 近期业绩（营收/利润增速）
- 估值水平（PE/PB是否合理）
- 财务健康度（负债率、现金流）

### 2. 题材热度（权重35%）
- 所属概念板块及题材正宗程度（是主业还是蹭概念）
- 当前市场对该题材的关注度和持续性
- 是否有近期催化剂（政策、事件、业绩）
- 题材的想象空间和天花板

### 3. 技术面/短线动能（权重30%）
- 近期K线形态（是否有启动信号）
- 量价配合情况
- 均线系统状态（多头/空头/缠绕）
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
