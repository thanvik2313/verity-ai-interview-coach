"""FastAPI application composition root.

Scope of this module (Task 2.1, Part A): app factory, lifespan-managed DB
engine startup/shutdown, CORS, security headers, typed-error exception
handlers, and an unauthenticated health check. No auth routes are mounted
yet — `GET /v1/auth/*` (API.md §3) arrives with the OAuth task, and this
module's `create_app()` is where that router will be `include_router`'d.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from verity.core.config import Settings, get_settings
from verity.core.errors import AuthenticationError, VerityError
from verity.db.session import dispose_engine, get_engine


def _register_exception_handlers(app: FastAPI) -> None:
    """Map the core error hierarchy to safe, minimal HTTP responses.

    Messages are deliberately generic — the typed exception hierarchy in
    `core.errors` exists so internal code can be specific while the HTTP
    boundary stays uninformative to a caller (Architecture.md §7).
    """

    @app.exception_handler(AuthenticationError)
    async def _handle_authentication_error(
        _request: Request, _exc: AuthenticationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "unauthorized", "message": "Authentication is required."},
        )

    @app.exception_handler(VerityError)
    async def _handle_verity_error(_request: Request, _exc: VerityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "bad_request", "message": "The request could not be completed."},
        )


def _add_security_headers(app: FastAPI) -> None:
    """Attach the baseline response headers required by Architecture.md §7.

    A full Content-Security-Policy is route-sensitive (report/share pages
    need a stricter policy) and is finalized alongside those routes in a
    later task; the headers here are safe and unconditional for every
    response in the meantime.
    """

    @app.middleware("http")
    async def _security_headers_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application instance.

    Args:
        settings: Override for tests; defaults to the cached process
            settings singleton.
    """
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        # Eagerly create the engine at startup rather than lazily on first
        # request, so a misconfigured DATABASE_URL fails the process at
        # boot instead of on a candidate's first request.
        get_engine()
        try:
            yield
        finally:
            await dispose_engine()

    app = FastAPI(
        title="Verity API",
        version="0.1.0",
        # Docs are useful in local/staging; disabled in production per the
        # edge-WAF/least-exposure posture in TechStack.md §5.
        docs_url="/docs" if app_settings.environment != "production" else None,
        redoc_url="/redoc" if app_settings.environment != "production" else None,
        openapi_url="/openapi.json" if app_settings.environment != "production" else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "Idempotency-Key"],
    )

    _add_security_headers(app)
    _register_exception_handlers(app)

    @app.get("/health", tags=["operations"])
    async def health() -> dict[str, str]:
        """Unauthenticated liveness/readiness signal.

        Deliberately reports only process-level status, not dependency
        internals (Architecture.md §9 — health endpoints avoid exposing
        internal details). A dependency-aware readiness check belongs under
        `/v1/admin/operations/health` (API.md §4), added with the
        operations module.
        """
        return {"status": "ok", "environment": app_settings.environment}

    return app


# Module-level instance for `uvicorn verity.main.app:app`.
app = create_app()
