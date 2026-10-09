

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from app.ai.agent.multi_agent.node.answer_node import answer_node
from app.ai.agent.multi_agent.node.evaluate_node import evaluate_node
from app.ai.agent.multi_agent.node.followup_node import followup_node
from app.ai.agent.multi_agent.node.manager_node import manager_node
from app.ai.agent.multi_agent.node.profile_node import profile_node
from app.ai.agent.multi_agent.node.question_node import question_node
from app.ai.agent.multi_agent.node.report_node import report_node
from app.ai.agent.multi_agent.state.reply_state import ReplyState


class ReplyGraph:

    def __init__(self) -> None:
        # 使用内存 Checkpointer 保存会话状态
        self.memory: InMemorySaver = InMemorySaver()
        # 编译图
        self.agent = self.reply_agent()

    def reply_agent(self) -> Any:
        graph = (StateGraph(ReplyState))
        """向图中注册所有节点。"""
        graph.add_node("profile",profile_node)
        graph.add_node("question",question_node)
        graph.add_node("answer",answer_node)
        graph.add_node("evaluate",evaluate_node)
        graph.add_node("followup",followup_node)
        graph.add_node("report",report_node)
        graph.add_node("manager",manager_node,
            destinations=(
                "profile",
                "question",
                "answer",
                "evaluate",
                "followup",
                "report",
                END,
            ),
        )
        # 图从 manager 开始
        graph.add_edge(START,"manager")
        graph.add_edge("profile","manager")
        graph.add_edge("question","manager")
        graph.add_edge("answer","manager")
        graph.add_edge("evaluate","manager")
        graph.add_edge("followup","manager")
        graph.add_edge("report","manager")

        self.agent = graph.compile(checkpointer=self.memory)
        return self.agent

    async def start(self,document_context: str,session_id: str,) -> dict[str, Any]:
        """
        开始一次新的答辩。
        参数：
            document_context：用户提交的项目资料文本。
            session_id：本次答辩会话编号。
        返回：
            当前图运行结束时的 State。
        """
        # 使用 session_id 隔离不同答辩会话的记忆
        config = {
            "configurable": {
                "thread_id": session_id,
            },
            "recursion_limit": 50,#最多执行 50 个节点步骤
        }

        # 第一次运行只传入项目资料
        initial_state: ReplyState = {
            "document_context": document_context,
            "reply_step": "start",
            "total_questions": 3,
            "max_followups": 3,
            "questions": [],
            "answers": [],
            "evaluations": [],
            "messages": [],
        }

        return await self.agent.ainvoke(initial_state,config=config)

    def get_state(self, session_id: str) -> dict[str, Any] | None:
        """
        获取当前进程内保存的答辩状态。

        当前图使用 InMemorySaver，因此这里只能恢复后端进程
        尚未重启时的状态；服务重启后会返回空状态。
        """

        config = {
            "configurable": {
                "thread_id": session_id,
            },
        }

        snapshot = self.agent.get_state(config)
        if snapshot is None:
            return None

        values = getattr(snapshot, "values", None)
        if not values:
            return None

        return dict(values)

    async def submit_answer(self,answer: str,session_id: str,) -> dict[str, Any]:
        """
        提交用户回答并恢复答辩流程。
        使用与 start 相同的 session_id，
        Checkpointer 会恢复之前保存的 State。
        """
        # 用户回答必须作为 HumanMessage 传入
        answer_input = {"messages": [HumanMessage(content=answer)]}
        # 恢复对应会话
        config = {
            "configurable": {"thread_id": session_id,},"recursion_limit": 50
        }

        return await self.agent.ainvoke(answer_input,config=config)




    def draw(self):
        data = self.agent.get_graph().draw_mermaid_png()
        with open("reply_graph.png", "wb") as f:
            f.write(data)
if __name__ == "__main__":
    import asyncio

    async def test_reply_graph() -> None:
        """完整测试三道主问题和追问流程。"""

        # 整个测试期间必须复用同一个 ReplyGraph 实例
        reply_graph = ReplyGraph()

        session_id = "test-session-full"

        document_context = """
        我开发了一个 AI 项目答辩与能力评测系统。

        系统后端使用 Python 和 FastAPI，
        使用 LangGraph 管理项目画像、问题生成、
        答案评价、连续追问和最终报告生成流程。

        项目资料经过文本切分后保存到 Chroma，
        答辩记录和评价结果保存到 MySQL。
        """

        # 第一次调用：生成项目画像和第一道主问题
        state = await reply_graph.start(
            document_context=document_context,
            session_id=session_id,
        )

        while True:
            reply_step = state.get(
                "reply_step",
                "",
            )

            print("\n当前流程：", reply_step)
            print(
                "当前问题：",
                state.get("current_question"),
            )

            # 报告生成后结束测试
            if reply_step == "report_completed":
                print("\n最终报告：")
                print(state.get("final_report"))
                break

            # 允许手动提前结束
            answer = input(
                "\n请输入回答，输入 exit 结束："
            )

            if answer.strip().lower() == "exit":
                print("测试结束")
                break

            # 提交回答并恢复同一个会话
            state = await reply_graph.submit_answer(
                answer=answer,
                session_id=session_id,
            )

            # 打印最近一次评价
            evaluations = state.get(
                "evaluations",
                [],
            )

            if evaluations:
                print("\n最近一次评价：")
                print(evaluations[-1])

    asyncio.run(test_reply_graph())
