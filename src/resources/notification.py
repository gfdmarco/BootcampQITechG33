from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import NotificationController


class NotificationResource:
    def on_get_list(self, request: Request) -> JSONResponse:
        controller = NotificationController()
        result = controller.list_for_customer(request.state.customer_key)

        return JSONResponse(
            content=jsonable_encoder(result),
            status_code=http_status.HTTP_200_OK,
        )

    def on_patch_read(self, key: str, request: Request) -> JSONResponse:
        controller = NotificationController()
        result = controller.mark_read(key, request.state.customer_key)

        return JSONResponse(
            content=jsonable_encoder(result),
            status_code=http_status.HTTP_200_OK,
        )
