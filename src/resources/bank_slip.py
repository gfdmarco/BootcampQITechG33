from fastapi import Request
from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import BankSlipController
from utils.schema_handler import SchemaHandler

DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0

class BankSlipResource:
    @SchemaHandler.validate("post_bank_slip.json")
    def on_post(self, account_key: str, payload: dict, request: Request) -> None:
        controller = BankSlipController()
        token_customer_key = request.state.customer_key

        bank_slip = controller.issue(account_key, token_customer_key, payload)

        return JSONResponse(
            content=jsonable_encoder(bank_slip),
            status_code=status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, bank_slip_key: str, request: Request) -> JSONResponse:
        controller = BankSlipController()
        token_customer_key = request.state.customer_key

        bank_slip = controller.get_by_key(bank_slip_key, token_customer_key)

        return JSONResponse(
            content=jsonable_encoder(bank_slip),
            status_code=status.HTTP_200_OK,
        )

    def on_post_webhook_paid(self, bank_slip_key: str) -> JSONResponse:
        """Chamado pelo SERVIÇO DE BOLETOS, não pelo cliente: sem JWT, só INTERNAL-TOKEN."""
        controller = BankSlipController()
        bank_slip = controller.pay(bank_slip_key)
        #nao precisa de customer_key pois é chamado de fora
        return JSONResponse(content=jsonable_encoder(bank_slip), status_code=status.HTTP_200_OK)

    @SchemaHandler.validate_query_params("get_bank_slips.json")
    def on_get_list(self, account_key: str, request: Request) -> JSONResponse:
        controller = BankSlipController()

        limit = int(request.query_params.get("limit", DEFAULT_LIMIT))
        page = int(request.query_params.get("page", DEFAULT_PAGE))
        offset = page * limit

        result = controller.list_by_account(account_key, request.state.customer_key, limit, offset)

        envelope = {
            "data": result["data"],
            "limit": limit,
            "page": page,
            "is_last_page": result["is_last_page"],
        }
        return JSONResponse(content=jsonable_encoder(envelope), status_code=status.HTTP_200_OK)