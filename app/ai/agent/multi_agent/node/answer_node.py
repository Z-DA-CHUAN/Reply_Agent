

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.ai.agent.multi_agent.state.reply_state import ReplyState


def answer_node(state: ReplyState,) -> dict[str, Any]:
    """
    收集用户对当前问题的回答，并保存到状态中。
    """
    # 获取当前正在回答的问题
    current_question: dict[str, Any] = state.get("current_question",{},)
    # 获取对话消息
    messages = state.get("messages", [])
    # print(messages)
    # 获取回答
    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage):
        raise ValueError("最后一条消息不是用户回答")
    # 获取用户回答文本
    answer_content: str = str(last_message.content).strip()

    if not answer_content:
        raise ValueError("用户回答不能为空")
    # 获取之前保存的答案
    answers = state.get("answers",[],)

    # 将问题和用户答案关联起来
    current_answer: dict[str, Any] = {
        "question_id": current_question.get("question_id"),
        "question_type": current_question.get("question_type"),
        "question_content": current_question.get("question_content","",),
        "answer_content": answer_content,
    }

    return {
        # 保存原来的答案和当前答案
        "answers": [
            *answers,
            current_answer,
        ],
        # 标记已经收到用户回答
        "reply_step": "answer_received",
        # 给用户一个简单确认消息
        "messages": [AIMessage(content="回答已记录")],
    }
