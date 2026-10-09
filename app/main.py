

from fastapi import FastAPI
from app.web.reply_router.reply_router import reply_router
from app.web.document_router.document_router import document_router
from app.web.websocket_router.websocket_router import websocket_router

# 创建 FastAPI 应用
app = FastAPI(
    title="Reply Agent",
    description="AI 项目答辩与能力评测系统",
    version="1.0.0",
)


# 注册答辩相关接口
app.include_router(reply_router)
# 注册项目文档上传接口
app.include_router(document_router)
# 注册语音识别 WebSocket
app.include_router(websocket_router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """
    健康检查接口。
    """

    return {
        "status": "ok",
        "service": "reply-agent",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
