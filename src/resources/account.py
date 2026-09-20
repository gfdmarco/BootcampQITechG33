from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import CustomerController
from utils.schema_handler import SchemaHandler


class AccountResource:
    @SchemaHandler.validate("post_customer_account.json")
    def on_post_open_account(self, customer_key: str, payload: dict, request: Request) -> JSONResponse:
        """Abre uma nova conta para o customer autenticado.

        A validação de negócio (limite de contas, existência do customer,
        JWT) é responsabilidade do CustomerController.
        """
        controller = CustomerController()
        token_customer_key = request.state.customer_key

        account = controller.open_account(customer_key, payload, token_customer_key)

        return JSONResponse(
            content=jsonable_encoder(account),
            status_code=status.HTTP_201_CREATED,
        )
