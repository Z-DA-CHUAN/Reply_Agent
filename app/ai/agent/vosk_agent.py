import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from vosk import KaldiRecognizer

from app.ai.models.my_models import MyModel


class VoskAgent:
    """
    浏览器语音识别服务。

    浏览器通过 WebSocket 发送 16kHz、单声道、16 位 PCM 音频，
    本类使用 Vosk 将音频转换成中文文本。模型本身由 MyModel
    复用，但每个 WebSocket 连接单独创建识别器，避免多个用户串音。
    """

    async def recognize(self, websocket: WebSocket) -> None:
        recognizer: KaldiRecognizer | None = None

        try:
            while True:
                message: dict[str, Any] = await websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    break

                # 前端用文本消息控制开始、停止；音频使用二进制消息。
                control = message.get("text")
                if control is not None:
                    try:
                        command = json.loads(control)
                    except json.JSONDecodeError:
                        command = {"action": control}

                    action = command.get("action")
                    if action == "start":
                        recognizer = KaldiRecognizer(
                            MyModel.get_vosk_model(),
                            16000,
                        )
                        await websocket.send_json({
                            "type": "ready",
                            "message": "语音识别已准备，可以开始说话",
                        })
                    elif action == "stop":
                        if recognizer is not None:
                            final_result = json.loads(recognizer.FinalResult())
                            final_text = str(final_result.get("text", "")).strip()
                            if final_text:
                                await websocket.send_json({
                                    "type": "final",
                                    "text": final_text,
                                })
                        await websocket.send_json({
                            "type": "stopped",
                            "message": "语音识别已停止",
                        })
                        break
                    continue

                audio_data = message.get("bytes")
                if not audio_data:
                    continue

                if recognizer is None:
                    recognizer = KaldiRecognizer(
                        MyModel.get_vosk_model(),
                        16000,
                    )

                if recognizer.AcceptWaveform(audio_data):
                    result = json.loads(recognizer.Result())
                    text = str(result.get("text", "")).strip()
                    if text:
                        await websocket.send_json({
                            "type": "final",
                            "text": text,
                        })
                else:
                    partial_result = json.loads(recognizer.PartialResult())
                    partial_text = str(partial_result.get("partial", "")).strip()
                    await websocket.send_json({
                        "type": "partial",
                        "text": partial_text,
                    })

        except WebSocketDisconnect:
            return
