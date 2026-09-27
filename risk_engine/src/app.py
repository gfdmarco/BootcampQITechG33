import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from database import open_context, clear_context
from resources import RiskResource

INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "risk_default_token")
BYPASS_ENDPOINTS = {"/health_check", "/"}


def create_app() -> FastAPI:
    application = FastAPI(
        title="Risk Engine API",
        description="Módulo isolado de análise antifraude e gestão de risco."
    )

    # ── Middlewares (lidos de baixo pra cima — último registrado, primeiro a rodar) ──
    @application.middleware("http")
    async def session_middleware(request: Request, call_next):
        context = open_context()
        request.state.context = context
        try:
            response = await call_next(request)
        finally:
            if context.db_session:
                context.db_session.close()
            clear_context()
        return response

    @application.middleware("http")
    async def internal_token_middleware(request: Request, call_next):
        if request.url.path in BYPASS_ENDPOINTS or request.method == "OPTIONS":
            return await call_next(request)
        if request.headers.get("INTERNAL-TOKEN") != INTERNAL_TOKEN:
            return JSONResponse(status_code=403, content={"error": "Forbidden"})
        return await call_next(request)

    # ── Rotas — o endereço, o verbo, e quem atende ──
    risk_resource = RiskResource()

    application.add_api_route("/health_check", lambda: {"status": "ok"}, methods=["GET"])
    application.add_api_route("/evaluate",                        risk_resource.on_post_evaluate,  methods=["POST"])
    application.add_api_route("/risk_profile/{customer_key}",     risk_resource.on_patch_profile,  methods=["PATCH"])
    application.add_api_route("/risk_profile/{customer_key}",     risk_resource.on_get_profile,    methods=["GET"])
    application.add_api_route("/risk_profile",                         risk_resource.on_get_profile_list, methods=["GET"])

    from errors import register_error_handlers
    register_error_handlers(application)

    return application


app = create_app()
