

import json
from typing import Any
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from app.ai.agent.multi_agent.schema.question_schema import QuestionSchema
from app.ai.agent.multi_agent.state.reply_state import ReplyState
from app.ai.models.my_models import MyModel
from app.ai.prompt.builder_prompt import BuilderPromptYaml


# 加载追问节点提示词
followup_prompt = (BuilderPromptYaml.get_prompt("followup_node.yaml"))


async def followup_node(state: ReplyState,) -> dict[str, Any]:
    """
    根据用户最近一次回答和评价生成一道追问。
    """

    # 获取项目画像
    project_profile = state.get("project_profile",{},)
    # 获取当前问题
    current_question = state.get("current_question",{},)

    # 获取答案记录和评价记录
    answers: list[dict[str, Any]] = state.get("answers",[],)
    evaluations: list[dict[str, Any]] = state.get("evaluations",[],)

    # 最近一次答案就是当前问题的答案
    current_answer: dict[str, Any] = answers[-1]

    # 最近一次评价就是当前答案的评价
    current_evaluation: dict[str, Any] = evaluations[-1]

    # 当前已经追问的次数
    followup_count: int = state.get("followup_count",0,)

    # 每道主问题最多追问三次
    max_followups: int = state.get("max_followups",3,)

    # 防止图路由错误导致超过追问次数
    if followup_count >= max_followups:
        raise ValueError("当前问题已经达到最大追问次数")

    # 下一次追问的次数
    next_followup_count: int = followup_count + 1

    # 获取已经提出过的所有问题
    questions: list[dict[str, Any]] = state.get("questions",[],)

    asked_questions: list[str] = []
    for question in questions:
        if question.get("question_content"):
            asked_questions.append(question.get("question_content", ""))

    # 优先使用 State 中的追问方向，
    # 如果没有，则使用最近一次评价中的追问方向
    followup_direction: str = state.get("followup_direction", "")
    if not followup_direction:
        followup_direction = current_evaluation.get("followup_direction", "")

    # 将数据填入追问提示词
    user_prompt: str = followup_prompt["user_prompt"].format(
        project_profile=json.dumps(project_profile,ensure_ascii=False,),
        current_question=json.dumps(current_question,ensure_ascii=False,),
        answer_content=current_answer.get("answer_content","",),
        evaluation_content=current_evaluation.get("evaluation_content","",),
        followup_direction=followup_direction,
        asked_questions=json.dumps(asked_questions,ensure_ascii=False,),
    )

    try:
        # 创建追问智能体
        followup_agent = create_agent(
            model=MyModel.get_model(),
            system_prompt=followup_prompt["system_prompt"],
            response_format=QuestionSchema,
        )

        # 调用追问智能体
        result = await followup_agent.ainvoke({"messages": [HumanMessage(content=user_prompt)]})

        # 获取结构化追问结果
        followup_result = (result["structured_response"])

    except Exception as error:
        raise RuntimeError(
            "追问生成失败"
        ) from error

    #当前问题的id
    current_question_id = str(current_question.get("question_id"))
    print(current_question_id)
    # print(current_question_id)
    #获取主问题的id
    parent_question_id = (current_question_id.split("-f", 1)[0])

    followup_question = {
        "question_id": (f"{parent_question_id}-f{next_followup_count}"),# 给追问生成独立编号，1-f1
        "question_content": (followup_result.question_content),
        "question_type": "followup",
    }

    return {
        # 保存原来的问题和新追问
        "questions": [
            *questions,
            followup_question,
        ],
        # 当前等待回答的问题变成这道追问
        "current_question": followup_question,
        # 追问次数加一
        "followup_count": next_followup_count,
        "reply_step": "waiting_answer",
        "messages": [AIMessage(
                content=followup_result.question_content
                )
            ],
    }
