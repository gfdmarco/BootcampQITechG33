from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import AccountController
from utils.schema_handler import SchemaHandler

DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0


class AccountsResource:
    def on_get_by_key(self, account_key: str) -> JSONResponse:
        controller = AccountController()
        account = controller.get_by_key(account_key)

        return JSONResponse(
            content=jsonable_encoder(account),
            status_code=http_status.HTTP_200_OK,
        )

    def on_get_balance(self, account_key: str, customer_key: str) -> JSONResponse:
        controller = AccountController()
        balance = controller.get_balance(customer_key, account_key)

        return JSONResponse(
            content=jsonable_encoder({"balance": balance}),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("put_accounts.json")
    def on_put_by_key(self, account_key: str, payload: dict) -> JSONResponse:
        controller = AccountController()
        account = controller.update_status(account_key, payload["status"])

        return JSONResponse(
            content=jsonable_encoder(account),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_accounts.json")
    def on_get_list(self, request: Request) -> JSONResponse:
        controller = AccountController()
        query_params = request.query_params

        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))

        filters = {
            "status_enumerators": query_params.getlist("status"),
            "branch": query_params.get("branch"),
            "number": query_params.get("number"),
            "account_type": query_params.get("account_type"),
            "balance_from": query_params.get("balance_from"),
            "date_from": query_params.get("date_from"),
            "date_to": query_params.get("date_to"),
        }

        offset = page * limit
        accounts_page = controller.get_list(limit, offset, filters)

        page_envelope = {
            "data": accounts_page["account_list_dto"],
            "limit": limit,
            "page": page,
            "is_last_page": accounts_page["is_last_page"],
        }

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_accounts_statement.json")
    def on_get_statement(self, request: Request, customer_key: str) -> JSONResponse:
        controller = AccountController()
        query_params = request.query_params

        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))

        filters = {
            "account_key": query_params.get("account_key"),
            "date_from": query_params.get("date_from"),
            "date_to": query_params.get("date_to"),
        }

        offset = page * limit
        statement_page = controller.get_statement(customer_key, limit, offset, filters)

        page_envelope = {
            "data": statement_page["transaction_list_dto"],
            "limit": limit,
            "page": page,
            "is_last_page": statement_page["is_last_page"],
        }

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )