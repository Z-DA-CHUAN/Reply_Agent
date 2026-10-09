

import json
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage
from app.ai.models.my_models import MyModel
from app.ai.prompt.builder_prompt import BuilderPromptYaml
from app.ai.agent.multi_agent.schema.question_schema import QuestionSchema
from app.ai.agent.multi_agent.state.reply_state import ReplyState


# 加载问题生成提示词
question_prompt = BuilderPromptYaml.get_prompt("question_node.yaml")
async def question_node(state: ReplyState,) -> dict[str, Any]:
    """
    根据项目画像生成一道答辩问题。
    """
    # 获取项目画像
    project_profile: dict[str, Any] = state.get("project_profile",{},)

    if not project_profile:
        raise ValueError("项目画像不能为空")

    # 获取已经生成的问题
    questions = state.get("questions",[],)

    # 提取已有问题
    asked_questions: list[str] = []
    for question in questions:
        if question.get("question_content"):
            asked_questions.append(question.get("question_content", ""))

    # 将项目画像和已有问题填入提示词
    user_prompt: str = question_prompt["user_prompt"].format(
        project_profile=json.dumps(project_profile, ensure_ascii=False,),#ensure_ascii=False是转义中文
        asked_questions=json.dumps(asked_questions, ensure_ascii=False,),
    )

    try:
        # 创建问题生成智能体
        question_agent = create_agent(
            model=MyModel.get_model(),
            system_prompt=question_prompt["system_prompt"],
            response_format=QuestionSchema,
        )
        # 调用智能体生成问题
        result = await question_agent.ainvoke({"messages": [HumanMessage(content=user_prompt)]})
        # print(result)
        # 获取结构化的问题结果
        question_result = (result["structured_response"])

    except Exception as error:
        raise RuntimeError(
            "答辩问题生成失败"
        ) from error

    # 计算已经生成的主问题数量
    main_question_count: int = 0
    for question in questions:
        if question.get("question_type") == "main":
            main_question_count += 1

    # 组装当前问题
    current_question: dict[str, Any] = {
        "question_id": main_question_count + 1,
        "question_content": (question_result.question_content),
        "question_type": "main",
    }

    return {
        "questions": [
            *questions,
            current_question,
        ],
        # 当前正在回答的问题
        "current_question": current_question,

        "followup_count": 0,
        "reply_step": "waiting_answer",
        "messages": [
            AIMessage(
                content=question_result.question_content
            )
        ],
    }
