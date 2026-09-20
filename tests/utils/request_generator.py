from os import environ

from tests.utils.requisition import ClientRequisition, BaseConnectorResponse


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


class RequestGenerator:
    @staticmethod
    def POST_sample_entity(sample_entity_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/sample_entity",
            payload=sample_entity_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )

        return response.response_status, response.response_json

    @staticmethod
    def GET_sample_entity(sample_entity_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET",
            f"/sample_entity/{sample_entity_key}",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_sample_entity(sample_entity_key: str, update_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/sample_entity/{sample_entity_key}",
            payload=update_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def PUT_webhook_sample_entity(sample_entity_key: str) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "PUT",
            f"/webhook/sample_entity/{sample_entity_key}/increment_counter",
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
        )
        return response.response_status, response.response_json

    @staticmethod
    def GET_sample_entities(params: dict = None) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "GET", "/sample_entities", headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}, query_params=params
        )
        return response.response_status, response.response_json

    @staticmethod
    def POST_customer(customer_payload: dict) -> BaseConnectorResponse:
        response = ClientRequisition.send(
            "POST",
            "/customers",
            payload=customer_payload,
            headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
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

