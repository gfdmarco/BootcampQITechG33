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

    @SchemaHandler.validate_query_params("get_customers.json")
    def on_get_list(self, request: Request) -> JSONResponse:
        controller = CustomerController()

        query_params = request.query_params

        limit = int(query_params.get("limit", 10))
        page = int(query_params.get("page", 0))

        filters = {
            "status_enumerators": query_params.getlist("status"),
            "name": query_params.get("name"),
            "email": query_params.get("email"),
            "document_number": query_params.get("document_number"),
        }

        offset = page * limit
        customers_page = controller.get_list(limit, offset, filters)

        page_envelope = {
            "data": customers_page["customers_list_dto"],
            "limit": limit,
            "page": page,
            "is_last_page": customers_page["is_last_page"],
        }

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
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

    def on_delete_by_key(self, customer_key: str, request: Request) -> JSONResponse:
        controller = CustomerController()
        token_customer_key = request.state.customer_key
        
        controller.delete(customer_key, token_customer_key)

        return JSONResponse(
            content=None,
            status_code=status.HTTP_204_NO_CONTENT,
        )
