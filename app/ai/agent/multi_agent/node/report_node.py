

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from app.ai.agent.multi_agent.schema.report_schema import ReportSchema
from app.ai.agent.multi_agent.state.reply_state import ReplyState
from app.ai.models.my_models import MyModel
from app.ai.prompt.builder_prompt import BuilderPromptYaml


# 加载最终报告提示词
report_prompt = BuilderPromptYaml.get_prompt("report_node.yaml")

async def report_node(state: ReplyState,) -> dict[str, Any]:
    """
    根据全部问题、回答和评价生成最终答辩报告。
    """

    # 获取生成报告所需的数据
    project_profile = state.get("project_profile",{},)
    questions = state.get("questions",[],)
    answers = state.get("answers",[],)
    evaluations = state.get("evaluations",[],)

    # 获取所有题目的评分
    scores = []
    for evaluation in evaluations:
        score = evaluation.get("score", 0)
        scores.append(score)

    # 计算所有回答的平均分
    score_sum = 0
    for score in scores:
        score_sum += score
    total_score = round(score_sum / len(scores)) if scores else 0

    # 将答辩数据填入提示词
    user_prompt = report_prompt["user_prompt"].format(
        project_profile=json.dumps(project_profile,ensure_ascii=False,),
        questions=json.dumps(questions,ensure_ascii=False,),
        answers=json.dumps(answers,ensure_ascii=False,),
        evaluations=json.dumps(evaluations,ensure_ascii=False,),
        total_score=total_score,
    )

    try:
        # 创建最终报告智能体
        report_agent = create_agent(
            model=MyModel.get_model(),
            system_prompt=report_prompt["system_prompt"],
            response_format=ReportSchema,
        )

        # 调用智能体生成报告
        result = await report_agent.ainvoke({"messages": [HumanMessage(content=user_prompt)]})

        # 获取结构化报告
        report_result = result["structured_response"]

    except Exception as error:
        raise RuntimeError(
            "最终答辩报告生成失败"
        ) from error

    # 组装最终报告
    final_report = {
        "total_score": total_score,
        # 下面的是提示词里让大模型生成的
        "overall_evaluation": (report_result.overall_evaluation),
        "advantages": report_result.advantages,
        "problems": report_result.problems,
        "suggestions": report_result.suggestions,
    }

    return {
        "final_report": final_report,
        "reply_step": "report_completed",
        "messages": [
            AIMessage(
                content="答辩完成，最终报告已生成"
            )
        ],
    }
