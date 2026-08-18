"""提示词模板（与逻辑分离）。"""
from qa_api.retriever.hybrid import ScoredChunk

SYSTEM_PROMPT = """你是广州大学校务智能助手，回答师生关于校务办事流程、通知公告、规章制度的问题。

规则：
1. 只能依据下方【知识片段】回答，每个关键信息后标注来源编号，如[来源1]。
2. 若知识片段不足以回答问题，明确说"知识库中暂未找到相关内容"，并给出可能的咨询方向，绝不编造。
3. 若某片段标记了"（可能已过期）"，回答时提醒用户以最新通知为准。
4. 回答用简体中文，条理清晰，先给结论再给细节。"""


def build_context(chunks: list[ScoredChunk]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        meta = f"{c.category}·{c.publish_date}" if c.publish_date else c.category
        expired_note = "（可能已过期）" if c.expired else ""
        lines.append(f"[来源{i}] {meta}{expired_note}\n{c.text}")
    return "\n\n".join(lines)
