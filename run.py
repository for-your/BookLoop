"""本地开发启动入口：python run.py"""
import uvicorn

from src.core.config import DEBUG, PROJECT_ROOT

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=DEBUG,
        reload_dirs=[str(PROJECT_ROOT / "src")] if DEBUG else None,
    )
