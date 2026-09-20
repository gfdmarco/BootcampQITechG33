from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import CustomerController
from utils.schema_handler import SchemaHandler


class CustomerResource:
    @SchemaHandler.validate("post_customer.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = CustomerController()
        customer = controller.create(payload)

        return JSONResponse(
            content=jsonable_encoder(customer),
            status_code=status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, customer_key: str) -> JSONResponse:
        controller = CustomerController()
        customer = controller.get_by_key(customer_key)

        return JSONResponse(
            content=jsonable_encoder(customer),
            status_code=status.HTTP_200_OK,
        )

    @SchemaHandler.validate("patch_customer.json")
    def on_patch_by_key(self, customer_key: str, payload: dict, request: Request) -> JSONResponse:
        controller = CustomerController()
        token_customer_key = request.state.customer_key
        
        customer = controller.update(customer_key, payload, token_customer_key)

        return JSONResponse(
            content=jsonable_encoder(customer),
            status_code=status.HTTP_200_OK,
        )
