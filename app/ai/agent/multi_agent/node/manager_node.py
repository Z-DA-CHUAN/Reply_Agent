

from typing import Any
from langchain_core.messages import AnyMessage, HumanMessage
from langgraph.graph import END
from langgraph.types import Command
from app.ai.agent.multi_agent.state.reply_state import ReplyState


def count_main_questions(questions) -> int:
    """
    统计已经生成的主问题数量。
    questions 中同时保存主问题和追问，
    所以这里只统计 question_type == "main" 的记录。
    """
    count: int = 0
    for question in questions:
        if question.get("question_type") == "main":
            count += 1
    return count

def manager_node(state: ReplyState,) -> Command:
    """
    根据当前答辩状态决定下一个节点。

    manager_node 不负责生成内容，
    只负责流程路由。
    """

    # 获取当前流程阶段
    reply_step = state.get("reply_step","start")
    # 获取项目画像
    project_profile = state.get("project_profile",{})
    # 获取历史问题
    questions = state.get("questions",[])
    # 本次答辩默认生成三道主问题
    total_questions = state.get("total_questions",3)
    # 当前主问题已经追问的次数
    followup_count: int = state.get("followup_count",0)
    # 每道主问题最多追问三次
    max_followups: int = state.get("max_followups",3,)
    # 评价节点给出的追问判断
    need_followup: bool = state.get("need_followup",False)
    # 获取消息历史
    messages: list[AnyMessage] = state.get("messages",[])
    # 获取最后一条消息
    last_message = None
    if messages:
        last_message = messages[-1]

    # 如果项目画像还没有生成，
    # 无论当前阶段是什么，都先生成项目画像
    if not project_profile:
        return Command(goto="profile")

    # 答辩已经完成，结束图运行
    if reply_step in {"report_completed","done"}:
        return Command(goto=END)

    # 项目画像生成完成后，生成第一道主问题
    if reply_step in {"start","profile_completed"}:
        return Command(goto="question")

    # 问题生成后等待用户回答
    if reply_step == "waiting_answer":
        # 如果最后一条消息是用户消息，
        # 说明用户已经提交回答，进入答案节点
        if isinstance(last_message, HumanMessage):
            return Command(goto="answer")
        # 最后一条仍然是 AI 问题，先结束本次运行，等待外部传入用户回答
        return Command(goto=END)

    # 答案节点保存回答后，进入评价节点
    if reply_step == "answer_received":
        return Command(goto="evaluate")

    # 评价完成后，决定追问、下一道主问题或最终报告
    if reply_step == "evaluated":
        # 只有评价认为需要追问，
        # 并且没有达到追问上限时，才进入追问节点
        # 是否允许追问：评价说需要，且次数没超限
        can_followup: bool = False
        if need_followup:
            if followup_count < max_followups:
                can_followup = True

        if can_followup:
            return Command(goto="followup")

        # 当前主问题不再追问，
        # 统计已经生成的主问题数量
        main_question_count: int = count_main_questions(questions)

        # 主问题还没有达到三道，生成下一道主问题
        if main_question_count < total_questions:
            return Command(goto="question")

        # 三道主问题全部完成，生成最终报告
        return Command(goto="report")

    # 出现未定义的流程状态时直接报错，
    # 防止图进入无法退出的循环
    raise ValueError(
        f"无法识别的答辩流程状态：{reply_step}"
    )
