from fastapi import Request
from fastapi.responses import JSONResponse

from controllers import RiskController


class RiskResource:
    """
    Camada HTTP do Risk Engine.
    Traduz Request → Controller → Response.
    Não contém regra de negócio — apenas parsing e serialização.
    """

    async def on_post_evaluate(self, request: Request) -> JSONResponse:
        payload          = await request.json()
        customer_key     = payload.get("customer_key")
        amount           = int(payload.get("amount", 0))
        transaction_type = payload.get("transaction_type", "transfer")

        controller = RiskController(request.state.context)
        result     = controller.evaluate(customer_key, amount, transaction_type)
        return JSONResponse(status_code=200, content=result)

    async def on_patch_profile(self, customer_key: str, request: Request) -> JSONResponse:
        payload = await request.json()
        score   = payload.get("score", "unknown")
        reason  = payload.get("reason", "LLM Worker classification")

        controller = RiskController(request.state.context)
        result     = controller.update_profile(customer_key, score, reason)
        return JSONResponse(status_code=200, content=result)

    async def on_get_profile(self, customer_key: str, request: Request) -> JSONResponse:
        controller = RiskController(request.state.context)
        result     = controller.get_profile(customer_key)
        return JSONResponse(status_code=200, content=result)

    async def on_get_profile_list(self, request: Request) -> JSONResponse:
        """Lista todos os perfis — usada pelo LLM Worker para descobrir clientes."""
        controller = RiskController(request.state.context)
        profiles   = controller.list_profiles()
        return JSONResponse(status_code=200, content={"profiles": profiles})
