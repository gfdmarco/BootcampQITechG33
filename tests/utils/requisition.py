import json
import re
from uuid import uuid4

from requests import request, Response
from requests.exceptions import ConnectionError as RequestsConnectionError
from os import environ


API_OFFLINE = (
    "Não consegui falar com a API em {base_url}.\n"
    "Ela precisa estar de pé pros testes rodarem. Suba com:  docker compose up"
)


# Rotas em que a API exige o header Idempotency-Key (UUID gerado por quem
# chama). Um cliente de verdade gera uma chave por operação e reaproveita a
# mesma só quando repete aquela operação. Os testes fazem igual: se o teste
# não mandou chave, mandamos uma nova a cada chamada.
_IDEMPOTENT_ROUTES = [
    re.compile(r"^/transactions/?$"),
    re.compile(r"^/customers/[^/]+/accounts/?$"),
    re.compile(r"^/loans/?$"),
]


def _with_idempotency_key(method: str, endpoint: str, headers: dict) -> dict:
    """Acrescenta Idempotency-Key nas rotas que exigem, se faltar.

    Para testar a ausência da chave, passe headers={"Idempotency-Key": None}:
    o None tira o header em vez de gerar um.
    """
    headers = dict(headers)
    if "Idempotency-Key" in headers:
        if headers["Idempotency-Key"] is None:
            del headers["Idempotency-Key"]
        return headers
    if method.upper() == "POST" and any(r.match(endpoint) for r in _IDEMPOTENT_ROUTES):
        headers["Idempotency-Key"] = str(uuid4())
    return headers


class ClientRequisition:
    @staticmethod
    def send(
        method,
        endpoint,
        payload=None,
        headers=None,
        data=None,
        cert=None,
        query_params=None,
        verify=True,
    ):

        if headers is None:
            headers = dict()
        headers = _with_idempotency_key(method, endpoint, headers)

        api_host = environ.get("SERVER_LOCALHOST", "0.0.0.0")
        api_port = environ.get("API_PORT", "3000")
        base_url = f"http://{api_host}:{api_port}"

        url = f"{base_url}{endpoint}"

        try:
            response = request(
                method.upper(),
                url,
                headers=headers,
                json=payload,
                data=data,
                cert=cert,
                verify=verify,
                params=query_params,
            )
        except RequestsConnectionError:
            raise RuntimeError(API_OFFLINE.format(base_url=base_url)) from None

        base_response = BaseConnectorResponse(
            endpoint=endpoint,
            method=method,
            payload=payload,
            headers=headers,
            response=response,
        )

        return base_response


class BaseConnectorResponse:
    def __init__(
        self,
        response: Response,
        endpoint: str,
        method: str,
        headers: dict,
        payload: dict,
    ) -> None:
        self.endpoint = endpoint
        self.method = method
        self.payload = payload
        self.headers = headers
        self.response = response
        self.response_content = response.content
        self.response_status = response.status_code

        self.response_json = None
        try:
            self.response_json = json.loads(self.response_content)
        except Exception as ex:
            print(ex)
            ...
            # logger warning
