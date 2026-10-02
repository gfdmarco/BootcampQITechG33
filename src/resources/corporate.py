from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers.corporate_controller import CorporateController
from utils.schema_handler import SchemaHandler


class CorporateResource:
    @SchemaHandler.validate("post_corporate.json")
    def on_post(self, payload: dict, request: Request) -> JSONResponse:
        controller = CorporateController()
        authenticated_customer_key = request.state.customer_key

        corporate_data = controller.create_corporate(payload, authenticated_customer_key)

        return JSONResponse(
            content=jsonable_encoder(corporate_data),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, corporate_key: str, request: Request) -> JSONResponse:
        controller = CorporateController()
        authenticated_customer_key = request.state.customer_key

        corporate_data = controller.get_details(corporate_key, authenticated_customer_key)

        if not corporate_data:
            return JSONResponse(content={"detail": "Not Found"}, status_code=404)

        return JSONResponse(
            content=jsonable_encoder(corporate_data),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("post_corporate_member.json")
    def on_post_member(self, payload: dict, corporate_key: str, request: Request) -> JSONResponse:
        controller = CorporateController()
        authenticated_customer_key = request.state.customer_key

        member_data = controller.add_member(corporate_key, payload, authenticated_customer_key)

        return JSONResponse(
            content=jsonable_encoder(member_data),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_delete_member(self, corporate_key: str, target_customer_key: str, request: Request) -> JSONResponse:
        controller = CorporateController()
        authenticated_customer_key = request.state.customer_key

        controller.remove_member(corporate_key, target_customer_key, authenticated_customer_key)

        return JSONResponse(
            content={},
            status_code=http_status.HTTP_204_NO_CONTENT,
        )

    def on_post_account(self, corporate_key: str, request: Request) -> JSONResponse:
        controller = CorporateController()
        authenticated_customer_key = request.state.customer_key

        account_data = controller.create_account(corporate_key, authenticated_customer_key)

        return JSONResponse(
            content=jsonable_encoder(account_data),
            status_code=http_status.HTTP_201_CREATED,
        )

    @SchemaHandler.validate("post_corporate_transfer.json")
    def on_post_transfer(self, corporate_key: str, payload: dict, request: Request) -> JSONResponse:
        controller = CorporateController()
        authenticated_customer_key = request.state.customer_key

        transfer_data = controller.request_transfer(corporate_key, payload, authenticated_customer_key)

        return JSONResponse(
            content=jsonable_encoder(transfer_data),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_post_approve_transfer(self, corporate_key: str, request_id: int, request: Request) -> JSONResponse:
        controller = CorporateController()
        authenticated_customer_key = request.state.customer_key

        approval_data = controller.approve_transfer(corporate_key, request_id, authenticated_customer_key)

        return JSONResponse(
            content=jsonable_encoder(approval_data),
            status_code=http_status.HTTP_200_OK,
        )
