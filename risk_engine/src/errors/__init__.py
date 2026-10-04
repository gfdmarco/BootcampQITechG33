from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

class RiskAPIError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str):
        self.status_code = status_code
        self.error_code  = error_code
        self.message     = message
        super().__init__(message)

class TransactionDeniedByRisk(RiskAPIError):
    def __init__(self, reason: str):
        super().__init__(403, "RISK001", f"Transaction denied: {reason}")

class ProfileNotFound(RiskAPIError):
    def __init__(self, customer_key: str):
        super().__init__(404, "RISK002", f"Risk profile not found for {customer_key}")

class InvalidScoreValue(RiskAPIError):
    def __init__(self, value: str):
        super().__init__(422, "RISK003", f"Invalid score value: {value}")


class InvalidIdempotencyKey(RiskAPIError):
    def __init__(self):
        super().__init__(409, "RISK004", "Evaluation key was already used with a different payload")


class EvaluationNotFound(RiskAPIError):
    def __init__(self, evaluation_key: str):
        super().__init__(404, "RISK005", f"Risk evaluation not found for {evaluation_key}")


def register_error_handlers(application: FastAPI) -> None:
    @application.exception_handler(RiskAPIError)
    async def handle_risk_api_error(request: Request, exception: RiskAPIError) -> JSONResponse:
        return JSONResponse(
            status_code=exception.status_code,
            content={"error_code": exception.error_code, "message": exception.message}
        )
