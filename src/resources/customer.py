from fastapi import status
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
