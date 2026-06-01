"""SSE (Server-Sent Events) 스트리밍 유틸리티.

동기 generator(stream_generate 등)를 비동기 SSE로 변환한다.
"""

import asyncio
import json
import queue
import threading
from typing import Any, Callable, Generator

from fastapi.responses import StreamingResponse


async def sse_from_sync_generator(
    gen_func: Callable[..., Generator[str, None, None]],
    **kwargs: Any,
):
    """동기 generator 함수를 SSE 이벤트 스트림으로 변환한다.

    gen_func를 별도 스레드에서 실행하고, 생성된 토큰을
    ``data: {"token": "..."}`` SSE 형식으로 yield한다.
    """
    q: queue.Queue = queue.Queue()

    def _producer():
        try:
            for token in gen_func(**kwargs):
                q.put(("token", token))
            q.put(("done", None))
        except Exception as e:
            q.put(("error", str(e)))

    thread = threading.Thread(target=_producer, daemon=True)
    thread.start()

    while True:
        try:
            msg_type, data = await asyncio.to_thread(q.get, timeout=180)
        except Exception:
            yield f"data: {json.dumps({'error': 'timeout'})}\n\n"
            break

        if msg_type == "token":
            yield f"data: {json.dumps({'token': data})}\n\n"
        elif msg_type == "done":
            yield f"data: {json.dumps({'done': True})}\n\n"
            break
        elif msg_type == "error":
            yield f"data: {json.dumps({'error': data})}\n\n"
            break


def create_sse_response(async_generator) -> StreamingResponse:
    """SSE async generator를 StreamingResponse로 래핑한다."""
    return StreamingResponse(
        async_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
