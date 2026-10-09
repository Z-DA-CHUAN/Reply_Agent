from typing import Any


from app.ai.agent.multi_agent.graph.reply_graph import ReplyGraph
from app.database.repository.reply_repository import ReplyRepository
from starlette.concurrency import run_in_threadpool
from app.ai.rag.project_rag import ProjectRAG

class ReplyService:
    """
    答辩业务服务。
    负责组织：
    1. LangGraph 答辩流程；
    2. MySQL 历史记录保存；
    3. 用户历史答辩查询。
    """

    def __init__(
        self,
        reply_graph: ReplyGraph | None = None,
        reply_repository: ReplyRepository | None = None,
        project_rag: ProjectRAG | None = None,
    ) -> None:
        """
        初始化答辩服务。
        ReplyGraph 和 ReplyRepository 会在应用启动时
        创建一次，然后在多个请求中复用。
        """

        # LangGraph 答辩图
        self.reply_graph = (
        reply_graph or ReplyGraph()
    )
        # MySQL 答辩记录
        self.reply_repository = (
            reply_repository or ReplyRepository()# 没有传入时，自动创建 Repository
        )

        # 项目 RAG 服务
        self.project_rag = (
            project_rag or ProjectRAG()
        )
    @staticmethod
    def build_thread_id(user_id: str,session_id: str,) -> str:
        """
        构造 LangGraph 的 thread_id。
        数据库中保存原始 session_id，
        LangGraph 使用 user_id:session_id，
        避免不同用户的会话状态发生冲突。
        """
        return f"{user_id}:{session_id}"

    async def start_reply(
        self,
        user_id: str,
        session_id: str,
        project_id: int,
        project_name: str = "",
    ) -> dict[str, Any]:
        """
        根据上传到 Chroma 的项目资料开始答辩。
        参数：
            user_id：当前用户编号。
            session_id：本次答辩编号。
            project_id：Chroma 中的项目集合编号。
            project_name：项目名称，可选。
        """

        if not user_id.strip():
            raise ValueError(
                "用户编号不能为空"
            )

        if not session_id.strip():
            raise ValueError(
                "答辩会话编号不能为空"
            )

        if project_id <= 0:
            raise ValueError(
                "project_id 必须大于 0"
            )

        # 检查答辩会话是否已经存在
        old_session = (
            self.reply_repository.get_session(
                session_id=session_id,
                user_id=user_id,
            )
        )

        if old_session is not None:
            raise ValueError(
                "答辩会话已经存在，不能重复创建"
            )

        # 从 Chroma 检索能够概括项目的资料
        search_results: list[
            dict[str, str | float]
        ] = await run_in_threadpool(
            self.project_rag.search,
            project_id,
            (
                "项目名称、项目主要功能、使用的技术栈、"
                "核心业务模块和主要技术难点"
            ),
            20,
        )

        if not search_results:
            raise ValueError(
                "没有找到项目资料，请先上传项目文档"
            )

        # 只取检索结果中的文本内容，
        # distance 只用于检索排序，不发送给大模型
        document_context: str = "\n\n".join(
            str(result["content"])
            for result in search_results
            if result.get("content")
        )

        if not document_context.strip():
            raise ValueError(
                "项目资料检索结果为空"
            )

        # LangGraph 使用 user_id:session_id，
        # 避免不同用户的会话状态冲突
        thread_id: str = self.build_thread_id(
            user_id=user_id,
            session_id=session_id,
        )

        # 使用检索到的项目资料启动答辩
        state: dict[str, Any] = (
            await self.reply_graph.start(
                document_context=document_context,
                session_id=thread_id,
            )
        )

        # 没有手工填写名称时，
        # 使用项目画像生成的项目名称
        project_profile: dict[str, Any] = (
            state.get("project_profile", {})
        )

        saved_project_name: str = (
            project_name.strip()
            or str(
                project_profile.get(
                    "project_name",
                    "未命名项目",
                )
            )
        )

        # 创建 MySQL 答辩历史记录
        self.reply_repository.create_session(
            session_id=session_id,
            user_id=user_id,
            project_name=saved_project_name,
            total_questions=state.get(
                "total_questions",
                3,
            ),
            max_followups=state.get(
                "max_followups",
                3,
            ),
        )

        return state

    async def resume_reply(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """
        恢复当前进程内尚未完成的答辩。

        InMemorySaver 只在当前后端进程中有效；如果服务已经重启，
        找不到 LangGraph 状态时会明确提示用户重新开始。
        """

        if not user_id.strip():
            raise ValueError(
                "用户编号不能为空"
            )

        if not session_id.strip():
            raise ValueError(
                "答辩会话编号不能为空"
            )

        session = self.reply_repository.get_session(
            session_id=session_id,
            user_id=user_id,
        )

        if session is None:
            raise ValueError(
                "答辩会话不存在，或当前用户无权访问"
            )

        if session.get("status") == "completed":
            raise ValueError(
                "这场答辩已经完成，不能继续答辩"
            )

        thread_id = self.build_thread_id(
            user_id=user_id,
            session_id=session_id,
        )

        state = await run_in_threadpool(
            self.reply_graph.get_state,
            thread_id,
        )

        if not state:
            raise ValueError(
                "当前进程中没有找到这场答辩状态，可能是后端已重启，请重新开始答辩"
            )

        if state.get("reply_step") in {
            "report_completed",
            "done",
        }:
            raise ValueError(
                "这场答辩已经完成，不能继续答辩"
            )

        return state

    async def submit_answer(
        self,
        user_id: str,
        session_id: str,
        answer: str,
    ) -> dict[str, Any]:
        """
        提交用户回答，恢复答辩流程，
        并保存本轮问题、回答和评价。
        """

        # 检查用户回答
        if not answer.strip():
            raise ValueError(
                "用户回答不能为空"
            )
        # 验证答辩会话属于当前用户
        session = self.reply_repository.get_session(
            session_id=session_id,
            user_id=user_id,
        )

        if session is None:
            raise ValueError(
                "答辩会话不存在，或当前用户无权访问"
            )

        # 使用和 start_reply 相同的 thread_id
        thread_id = self.build_thread_id(
            user_id=user_id,
            session_id=session_id,
        )

        # 恢复 LangGraph 答辩流程
        state = await self.reply_graph.submit_answer(answer=answer,session_id=thread_id,)

        # 保存本轮最新的问答评价
        self._save_latest_record(
            user_id=user_id,
            session_id=session_id,
            state=state,
        )

        # 如果答辩已经完成，保存最终报告
        if state.get("reply_step") == "report_completed":
            self._complete_session(
                session_id=session_id,
                state=state,
            )

        return state

    def _save_latest_record(
        self,
        user_id: str,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        """
        保存当前 State 中最新的一轮评价记录。

        每次用户提交回答后，
        evaluate_node 会在 evaluations 末尾追加一条记录。
        """

        evaluations = state.get("evaluations", [])

        # 当前还没有评价时，不保存记录
        if not evaluations:
            return

        latest_evaluation = evaluations[-1]

        question_id = latest_evaluation.get("question_id")

        if question_id is None:
            raise ValueError(
                "评价记录缺少 question_id"
            )

        # 查询已有记录，避免重复提交时重复插入
        old_records = (
            self.reply_repository.get_session_records(
                session_id=session_id,
                user_id=user_id,
            )
        )

        for record in old_records:
            if str(record.get("question_id")) == str(
                question_id
            ):
                return

        # 新记录的顺序
        sequence_no: int = len(old_records) + 1

        # 写入 reply_record
        self.reply_repository.save_record(
            session_id=session_id,
            sequence_no=sequence_no,
            question_id=question_id,
            question_type=str(latest_evaluation.get("question_type","main")),
            question_content=str(latest_evaluation.get("question_content","")),
            answer_content=latest_evaluation.get("answer_content"),
            score=latest_evaluation.get("score"),
            evaluation_content=latest_evaluation.get("evaluation_content"),
            need_followup=bool(latest_evaluation.get("need_followup",False)),
            followup_direction=latest_evaluation.get("followup_direction"),
        )

    def _complete_session(
        self,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        """
        将最终报告保存到 reply_session。
        """

        final_report = state.get("final_report", {})

        self.reply_repository.complete_session(
            session_id=session_id,
            total_score=int(final_report.get("total_score",0)),
            overall_evaluation=str(final_report.get("overall_evaluation","")),
            advantages=list(final_report.get("advantages",[])),
            problems=list(final_report.get("problems",[])),
            suggestions=list(final_report.get("suggestions",[])),
        )

    def delete_reply_history(
        self,
        user_id: str,
        session_id: str,
    ) -> bool:
        """删除当前用户指定的一场答辩历史。"""

        if not user_id.strip():
            raise ValueError(
                "用户编号不能为空"
            )

        if not session_id.strip():
            raise ValueError(
                "答辩会话编号不能为空"
            )

        return self.reply_repository.delete_session(
            session_id=session_id,
            user_id=user_id,
        )

    def get_user_sessions(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """
        查询用户的历史答辩列表。
        """

        if not user_id.strip():
            raise ValueError(
                "用户编号不能为空"
            )

        return self.reply_repository.get_user_sessions(
            user_id=user_id
        )

    def get_reply_detail(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any] | None:
        """
        查询某场答辩的完整详情。

        返回：

        {
            "session": {...},
            "records": [...]
        }
        """

        session = self.reply_repository.get_session(
            session_id=session_id,
            user_id=user_id,
        )

        if session is None:
            return None

        records = (
            self.reply_repository.get_session_records(
                session_id=session_id,
                user_id=user_id,
            )
        )

        return {
            "session": session,
            "records": records,
        }
