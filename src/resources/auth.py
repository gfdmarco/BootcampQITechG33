from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import AuthController
from utils.schema_handler import SchemaHandler


class AuthResource:
    @SchemaHandler.validate("post_auth_login.json")
    def on_post_login(self, payload: dict) -> JSONResponse:
        controller = AuthController()
        token_data = controller.login(payload)

        return JSONResponse(
            content=jsonable_encoder(token_data),
            status_code=status.HTTP_200_OK,
        )

    @SchemaHandler.validate("post_auth_refresh.json")
    def on_post_refresh(self, payload: dict) -> JSONResponse:
        controller = AuthController()
        token_data = controller.refresh(payload)

        return JSONResponse(
            content=jsonable_encoder(token_data),
            status_code=status.HTTP_200_OK,
        )

    @SchemaHandler.validate("put_auth_password.json")
    def on_put_password(self, payload: dict, request: Request) -> JSONResponse:
        controller = AuthController()
        token_customer_key = request.state.customer_key
        
        controller.update_password(payload, token_customer_key)

        return JSONResponse(
            content=jsonable_encoder({"message": "Password successfully updated."}),
            status_code=status.HTTP_200_OK,
        )

