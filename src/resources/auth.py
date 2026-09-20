from fastapi import status
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
