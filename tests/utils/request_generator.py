from os import environ

from tests.utils.requisition import ClientRequisition, BaseConnectorResponse


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")

class RequestGenerator:
    @staticmethod
    def POST_customer(customer_payload: dict, idempotency_key: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        response = ClientRequisition.send(
            "POST",
            "/customers",
            payload=customer_payload,
            headers=headers,
        )

        return response.response_status, response.response_json

    @staticmethod
    def GET_customer(customer_key: str, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "GET",
            f"/customers/{customer_key}",
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_customers_list(params: dict = None, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
            
        # Converter dicionario de params para query string simples
        query_string = ""
        if params:
            import urllib.parse
            query_string = "?" + urllib.parse.urlencode(params, doseq=True)

        response = ClientRequisition.send(
            "GET",
            f"/customers{query_string}",
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def PATCH_customer(customer_key: str, payload: dict, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "PATCH",
            f"/customers/{customer_key}",
            payload=payload,
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def DELETE_customer(customer_key: str, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "DELETE",
            f"/customers/{customer_key}",
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_customer_account(customer_key: str, payload: dict, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "POST",
            f"/customers/{customer_key}/accounts",
            payload=payload,
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_auth_login(payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/auth/login",
            payload=payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_auth_refresh(payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/auth/refresh",
            payload=payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_auth_password(payload: dict, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "PUT",
            "/auth/password",
            payload=payload,
            headers=headers,
        )
        return response.response_status, response.response_json


    @staticmethod
    def GET_accounts(access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "GET",
            "/accounts",
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_account(account_key: str, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "GET",
            f"/accounts/{account_key}",
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_account(account_key: str, payload: dict, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "PUT",
            f"/accounts/{account_key}",
            payload=payload,
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_transaction(payload: dict, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        response = ClientRequisition.send(
            "POST",
            "/transactions",
            payload=payload,
            headers=headers,
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_account_statement(account_key: str, params: dict = None, access_token: str = None) -> BaseConnectorResponse:
        headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        query_string = ""
        if params:
            import urllib.parse
            query_string = "?" + urllib.parse.urlencode(params, doseq=True)

        response = ClientRequisition.send(
            "GET",
            f"/accounts/{account_key}/statement{query_string}",
            headers=headers,
        )
        return response.response_status, response.response_json
