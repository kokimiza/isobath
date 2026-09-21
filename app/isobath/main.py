import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .inference import artifact
from .routers import account, meta, position, surveys

MAX_BODY = 64 * 1024

log = logging.getLogger("isobath")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def create_app(model: artifact.Model | None = None) -> FastAPI:
    s = get_settings()
    app = FastAPI(title="ISOBATH API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.model = model or artifact.load(s.models_dir)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.origins,  # never "*" (SEC-NET-03)
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    @app.middleware("http")
    async def guard(request: Request, call_next):
        start = time.perf_counter()
        request.state.user_hash = None
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > MAX_BODY):  # NFR-LIM-01
            response = _error(413, "body_too_large")
        else:
            response = await call_next(request)
        if request.url.path.startswith("/v1/me"):
            response.headers["Cache-Control"] = "private, no-store"
        # one JSON line per request; never headers, bodies or tokens (SEC-LOG)
        log.info(
            json.dumps(
                {
                    "request_id": uuid.uuid4().hex[:12],
                    "user_hash": request.state.user_hash,
                    "endpoint": request.url.path,
                    "method": request.method,
                    "status": response.status_code,
                    "latency_ms": round((time.perf_counter() - start) * 1000),
                }
            )
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) else {"code": str(exc.detail)}
        return JSONResponse({"error": detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return _error(422, "invalid_request")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.error("unhandled", exc_info=exc)
        return _error(500, "internal_error")

    for r in (meta.router, surveys.router, position.router, account.router):
        app.include_router(r)
    return app


def _error(status: int, code: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": code}}, status_code=status)


app = create_app()
