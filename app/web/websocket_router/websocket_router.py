from fastapi import APIRouter, WebSocket

from app.ai.agent.vosk_agent import VoskAgent


websocket_router = APIRouter(tags=["websocket"])


@websocket_router.websocket("/ws/voice")
async def voice_recognition(websocket: WebSocket) -> None:
    """接收浏览器 PCM 音频并返回 Vosk 识别文本。"""

    await websocket.accept()
    try:
        await VoskAgent().recognize(websocket)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
