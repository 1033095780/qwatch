"""python -m backend -> 启动 API + 前端静态文件。"""

import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host=os.environ.get("QWATCH_HOST", "127.0.0.1"),
        port=int(os.environ.get("QWATCH_PORT", "8080")),
        reload=False,
    )
