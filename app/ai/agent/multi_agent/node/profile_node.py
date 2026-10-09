from typing import Any
from langchain_core.messages import AIMessage, HumanMessage,SystemMessage
from app.ai.models.my_models import MyModel
from app.ai.prompt.builder_prompt import BuilderPromptYaml
from app.ai.agent.multi_agent.schema.project_profile import ProjectProfileSchema
from app.ai.agent.multi_agent.state.reply_state import ReplyState
from langchain.agents import create_agent

# 加载项目画像节点的提示词
profile_prompt = BuilderPromptYaml.get_prompt("profile_node.yaml")

async def profile_node(state: ReplyState,) -> dict[str, Any]:
    # 将当前项目资料填入用户提示词模板
    user_prompt: str = profile_prompt["user_prompt"].format(
        project_name=state.get("project_name", ""),
        project_introduce=state.get("project_introduce", ""),
        project_technology=", ".join(state.get("project_technology", [])),
        document_context=state.get("document_context","",),
    )

    try:
        # 获取大模型
        model = MyModel.get_model()
        # 返回结构化结果
        profile_agent = create_agent(
        model =model,
        system_prompt=profile_prompt["system_prompt"],
        response_format=ProjectProfileSchema
    )
        result = await profile_agent.ainvoke({"messages": [HumanMessage(content=user_prompt)]})
        # print(result)
        profile_result= (result["structured_response"])
        # print(profile_result)

    except Exception as error:
        raise RuntimeError(
            "项目画像生成失败"
        ) from error

    # 返回需要更新的状态
    return {
        # 将 Pydantic 模型转换成普通字典
        "project_profile": profile_result.model_dump(),
        # 标记项目画像生成完成
        "reply_step": "profile_completed",
        # 保存一条流程消息
        "messages": [
            AIMessage(content="项目画像生成完成")
        ],
    }

if __name__ == "__main__":
    import asyncio
    async def test() -> None:
        test_state: ReplyState = {
            "document_context": """
            我开发了一个 AI 项目答辩与能力评测系统。

            系统后端使用 Python 和 FastAPI，通过 LangGraph
            管理项目画像生成、问题生成、答案评价、连续追问
            和最终报告生成流程。

            项目使用 Chroma 保存项目文档向量，使用 MySQL
            保存答辩记录和评价结果。
            """
        }
        await profile_node(test_state)
    asyncio.run(test())
