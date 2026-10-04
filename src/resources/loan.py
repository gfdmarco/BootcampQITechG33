from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi import Request, Response

from controllers.loan_controller import LoanController
from utils.idempotency import read_idempotency_key
from utils.schema_handler import SchemaHandler

class LoanResource:
    """A porta de entrada HTTP para empréstimos."""

    @SchemaHandler.validate("post_loans_simulate.json")
    def on_post_simulate(self, payload: dict, request: Request) -> JSONResponse:
        controller = LoanController()
        authenticated_customer_key = request.state.customer_key

        sim_data = controller.simulate_loan(
            account_key=payload["account_key"],
            requested_amount=payload["requested_amount"],
            installments_count=payload["installments_count"],
            authenticated_customer_key=authenticated_customer_key
        )

        return JSONResponse(
            content=jsonable_encoder(sim_data),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate("post_loans.json")
    def on_post(self, payload: dict, request: Request) -> JSONResponse:
        controller = LoanController()
        authenticated_customer_key = request.state.customer_key

        idempotency_key = read_idempotency_key(request)   # header obrigatório (UUID)

        loan = controller.create_loan(
            account_key=payload["account_key"],
            requested_amount=payload["requested_amount"],
            installments_count=payload["installments_count"],
            authenticated_customer_key=authenticated_customer_key,
            idempotency_key=idempotency_key,
        )

        return JSONResponse(
            content=jsonable_encoder(loan),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_post_pay_installment(self, loan_key: str, installment_id: int, request: Request) -> JSONResponse:
        controller = LoanController()
        authenticated_customer_key = request.state.customer_key

        controller.pay_installment(loan_key, installment_id, authenticated_customer_key)
        
        return Response(status_code=http_status.HTTP_204_NO_CONTENT)
