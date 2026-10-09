from typing import Any, Annotated

from typing_extensions import TypedDict
from langchain_core.messages import AnyMessage
import operator


"""
答辩智能体的节点。

"""
class ReplyState(TypedDict, total=False):

    # 对话消息列表。
    messages: Annotated[list[AnyMessage], operator.add]

    # 用户编号，用于区分不同用户。
    user_id: str

    # 项目编号，用于关联项目资料。
    project_id: int
    # 本次答辩会话编号。
    session_id: str
    # 项目名称。
    project_name: str
    # 用户填写的项目简介。
    project_introduce: str
    # 项目技术栈
    project_technology: list[str]
    # 检索出来的资料。
    document_context: str
    #项目画像。
    project_profile: dict[str, Any]
    # 本次答辩需要生成的主问题数量。
    total_questions: int
    # 已经生成过的主问题和追问。
    questions: list[dict[str, Any]]
    # 当前正在回答的问题。
    current_question: dict[str, Any]
    # 用户提交的答案记录。
    answers: list[dict[str, Any]]
    # 每道题对应的评价结果。
    evaluations: list[dict[str, Any]]
    # 当前主问题已经追问的次数。
    followup_count: int
    # 每道主问题允许的最大追问次数。
    max_followups: int
    # 当前回答是否需要继续追问。
    need_followup: bool
    # 下一次追问应该关注的方向。
    followup_direction: str
    # 当前答辩流程所在阶段。
    # start              刚开始
    # profile_completed  项目画像生成完成
    # plan_completed     答辩计划生成完成
    # waiting_answer     已提出问题，等待用户回答
    # answer_received    已收到用户答案
    # evaluated          当前回答评价完成
    # report_completed   最终报告生成完成
    # done               整个答辩结束
    reply_step: str

    # 所有问题完成后生成的最终答辩报告。
    final_report: dict[str, Any]
