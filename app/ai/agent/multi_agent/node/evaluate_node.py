

import json
from typing import Any
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from app.ai.agent.multi_agent.schema.evaluation_schema import EvaluationSchema
from app.ai.agent.multi_agent.state.reply_state import ReplyState
from app.ai.models.my_models import MyModel
from app.ai.prompt.builder_prompt import BuilderPromptYaml


# 加载回答评价提示词
evaluate_prompt = BuilderPromptYaml.get_prompt("evaluate_node.yaml")

async def evaluate_node(state: ReplyState,) -> dict[str, Any]:
    """
    评价用户对当前问题的回答，
    并判断是否需要继续追问。
    """
    # 获取项目画像
    project_profile = state.get("project_profile",{},)
    # 获取当前问题
    current_question: dict[str, Any] = state.get("current_question",{},)
    # 获取所有用户答案
    answers: list[dict[str, Any]] = state.get("answers",[],)
    # 最后一条答案就是当前问题对应的回答
    current_answer: dict[str, Any] = answers[-1]
    answer_content: str = current_answer.get("answer_content","",)
    # 当前已经追问的次数
    followup_count: int = state.get("followup_count",0,)
    # 每道主问题最多追问3次
    max_followups: int = state.get("max_followups",3,)
    # 将评价需要的数据填入提示词
    user_prompt: str = evaluate_prompt["user_prompt"].format(
        project_profile=json.dumps(project_profile,ensure_ascii=False,),#ensure_ascii=False是转义中文
        current_question=json.dumps(current_question,ensure_ascii=False,),
        answer_content=answer_content,
        followup_count=followup_count,
        max_followups=max_followups,
    )

    try:
        # 创建回答评价智能体
        evaluate_agent = create_agent(
            model=MyModel.get_model(),
            system_prompt=evaluate_prompt["system_prompt"],
            response_format=EvaluationSchema,
        )

        # 调用评价智能体
        result = await evaluate_agent.ainvoke({"messages": [HumanMessage(content=user_prompt)]})
        # 获取结构化评价结果
        evaluation_result = (result["structured_response"])

    except Exception as error:
        raise RuntimeError(
            "用户回答评价失败"
        ) from error

    # 同时满足以下条件才允许追问：
    # 1. 大模型认为需要追问
    # 2. 当前追问次数没有达到上限
    need_followup = False
    if evaluation_result.need_followup:
        if followup_count < max_followups:
            need_followup = True
    else:
        need_followup = False
    # 如果不允许继续追问，就清空追问方向
    followup_direction = ""
    if need_followup:
        followup_direction = evaluation_result.followup_direction
    # 组装当前问题的评价记录
    # print(current_question)
    current_evaluation = {
        "question_id": current_question.get("question_id"),
        "question_type": current_question.get("question_type"),
        "question_content": current_question.get("question_content","",),
        "answer_content": answer_content,
        "score": evaluation_result.score,
        "evaluation_content": evaluation_result.evaluation_content,
        "need_followup": need_followup,
        "followup_direction": followup_direction,
    }

    # 获取之前的评价记录
    evaluations = state.get("evaluations",[],)

    return {
        # 保存原有评价和本次评价
        "evaluations": [
            *evaluations,
            current_evaluation,
        ],

        # 供后续路由判断是否进入追问节点
        "need_followup": need_followup,

        # 供追问节点生成具体追问
        "followup_direction": followup_direction,

        # 标记当前回答已经评价完成
        "reply_step": "evaluated",

        # 将评价内容加入消息历史
        "messages": [
            AIMessage(content=(evaluation_result.evaluation_content))
        ],
    }
