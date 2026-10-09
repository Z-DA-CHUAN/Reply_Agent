from typing import Any


from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.service.reply_service import ReplyService


# 创建答辩路由
reply_router = APIRouter(
    prefix="/api/replies",
    tags=["replies"],
)


# 创建答辩服务对象
# 整个应用运行期间复用同一个 ReplyService，
# 这样 ReplyGraph 中的 InMemorySaver 才能持续保存状态
reply_service = ReplyService()


class StartReplyRequest(BaseModel):
    """
    开始答辩的请求参数。

    项目资料需要先通过文档上传接口
    写入 project_id 对应的 Chroma 集合。
    """

    # 当前用户编号
    user_id: str = Field(
        min_length=1,
        description="用户编号",
    )

    # 本次答辩会话编号
    session_id: str = Field(
        min_length=1,
        description="答辩会话编号",
    )

    # 上传文档时使用的项目编号
    project_id: int = Field(
        gt=0,#表示 project_id 必须大于 0
        description="项目编号",
    )

    # 项目名称，可以不传
    # 不传时使用项目画像生成的名称
    project_name: str = Field(
        default="",
        description="项目名称",
    )

class SubmitAnswerRequest(BaseModel):
    """
    提交回答的请求参数。
    """
    # 当前用户编号
    user_id: str = Field(
        min_length=1,
        description="用户编号",
    )

    # 用户对当前问题的回答
    answer: str = Field(
        min_length=1,
        description="用户回答",
    )


def build_state_response(
    state: dict[str, Any],
) -> dict[str, Any]:
    """
    从 LangGraph State 中提取可以返回给前端的数据。

    不直接返回 messages，
    因为 messages 中包含 AIMessage 和 HumanMessage 对象。
    """

    return {
        # 当前答辩流程状态
        "reply_step": state.get("reply_step",""),

        # 当前等待用户回答的问题
        "current_question": state.get("current_question"),

        # 已经生成的问题
        "questions": state.get("questions",[]),

        # 已经提交的回答
        "answers": state.get("answers",[]),

        # 已经完成的评价
        "evaluations": state.get("evaluations",[]),

        # 答辩完成后生成的报告
        "final_report": state.get("final_report")}


@reply_router.post("/start")
async def start_reply(
    request: StartReplyRequest,
) -> dict[str, Any]:
    """
    开始一次新的答辩。
    """

    try:
        # 调用 Service 启动 LangGraph
        state = await reply_service.start_reply(
            user_id=request.user_id,
            session_id=request.session_id,
            project_id=request.project_id,
            project_name=request.project_name,
        )

        return build_state_response(state)

    except ValueError as error:
        # 参数错误、会话重复等业务异常
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        # 其他未预期异常
        raise HTTPException(
            status_code=500,
            detail="启动答辩失败",
        ) from error


@reply_router.post("/{session_id}/answer")
async def submit_answer(
    session_id: str,
    request: SubmitAnswerRequest,
) -> dict[str, Any]:
    """
    提交用户回答，并恢复答辩流程。
    """

    try:
        # 调用 Service 恢复 LangGraph
        state = await reply_service.submit_answer(
                user_id=request.user_id,
                session_id=session_id,
                answer=request.answer,
            )

        return build_state_response(state)

    except ValueError as error:
        # 空回答、会话不存在或无权访问
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="提交回答失败",
        ) from error


@reply_router.get("/history")
def get_reply_history(
    user_id: str = Query(
        min_length=1,
        description="用户编号",
    ),
) -> dict[str, Any]:
    """
    查询用户的历史答辩列表。
    """

    try:
        sessions = reply_service.get_user_sessions(user_id=user_id,)

        return {
            "user_id": user_id,
            "sessions": sessions,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="查询答辩历史失败",
        ) from error


@reply_router.delete("/{session_id}")
def delete_reply_history(
    session_id: str,
    user_id: str = Query(
        min_length=1,
        description="用户编号",
    ),
) -> dict[str, Any]:
    """删除当前用户的一场答辩历史及其全部问答记录。"""

    try:
        deleted = reply_service.delete_reply_history(
            user_id=user_id,
            session_id=session_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="答辩记录不存在，或当前用户无权删除",
            )

        return {
            "message": "答辩历史删除成功",
            "session_id": session_id,
        }

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="删除答辩历史失败",
        ) from error


@reply_router.get("/{session_id}/resume")
async def resume_reply(
    session_id: str,
    user_id: str = Query(
        min_length=1,
        description="用户编号",
    ),
) -> dict[str, Any]:
    """恢复当前进程内尚未完成的答辩。"""

    try:
        state = await reply_service.resume_reply(
            user_id=user_id,
            session_id=session_id,
        )
        return build_state_response(state)

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="恢复答辩失败",
        ) from error


@reply_router.get("/{session_id}")
def get_reply_detail(
    session_id: str,
    user_id: str = Query(
        min_length=1,
        description="用户编号",
    ),
) -> dict[str, Any]:
    """
    查询某场答辩的完整详情。

    返回：
        这场答辩的基本信息、最终总结和完整聊天记录。
    """

    try:
        detail = (
            reply_service.get_reply_detail(
                user_id=user_id,
                session_id=session_id,
            )
        )

        # 查不到可能是会话不存在，
        # 也可能是当前用户无权访问
        if detail is None:
            raise HTTPException(
                status_code=404,
                detail="答辩记录不存在",
            )

        return detail

    except HTTPException:
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="查询答辩详情失败",
        ) from error
