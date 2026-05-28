from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from core.config import settings
from core.logger import logger
from api.pr_review import  pr_review_router
from api.code_editor import router as code_editor_router
import os
import sys

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

app.include_router(pr_review_router, prefix=settings.API_V1_STR, tags=["PR Review"])
app.include_router(code_editor_router, prefix=settings.API_V1_STR, tags=["Code Editor"])



@app.get("/")
async def redirect_to_swagger():
    """Automatically redirect the root URL to the Swagger documentation page."""
    return RedirectResponse(url="/docs")

@app.on_event("startup")
async def startup_event() -> None:
    logger.info("LOCAL AI Agent Engine starting...")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("Shutting down LOCAL AI Agent Engine...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
