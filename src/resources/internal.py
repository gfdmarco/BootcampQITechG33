from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from constants import RISK_INTERNAL_TOKEN
from controllers import TransactionController
from errors import ForbiddenAction
from utils.schema_handler import SchemaHandler

DEFAULT_DAYS = 30
DEFAULT_LIMIT = 50


class InternalResource:
    """Rotas de serviço para serviço (prefixo /internal/).

    Quem chama não é um cliente, é o LLM Worker do Motor de Risco. Por
    isso não há JWT: a identidade de quem pede é provada pelo header
    RISK-WORKER-TOKEN, que tem de bater com o RISK_INTERNAL_TOKEN — um
    segredo que só o Core e o Motor de Risco conhecem. O INTERNAL-TOKEN
    continua obrigatório (o middleware cobra), mas sozinho não basta:
    todo cliente da API também manda ele.
    """

    @SchemaHandler.validate_query_params("get_internal_customer_transactions.json")
    def on_get_customer_transactions(self, customer_key: str, request: Request) -> JSONResponse:
        if request.headers.get("RISK-WORKER-TOKEN") != RISK_INTERNAL_TOKEN:
            raise ForbiddenAction()

        days = int(request.query_params.get("days", DEFAULT_DAYS))
        limit = int(request.query_params.get("limit", DEFAULT_LIMIT))

        history = TransactionController().list_recent_for_risk(customer_key, days, limit)

        return JSONResponse(
            content=jsonable_encoder(history),
            status_code=http_status.HTTP_200_OK,
        )