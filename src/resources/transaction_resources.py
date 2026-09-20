from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import TransactionController
from utils.schema_handler import SchemaHandler

DEFAULT_LIMIT = 10
DEFAULT_PAGE = 0


class TransactionResource:
    """A porta de entrada HTTP da Transação.

    Segue o mesmo desenho do `SampleEntityResource`: confere o corpo
    via schema, chama o controller, devolve o que ele respondeu. Nenhum
    `self.alguma_coisa`, nenhum SQL, nenhuma regra de negócio aqui.

    ────────────────────────────────────────────────────────────────
    A DIFERENÇA PARA O SAMPLE: QUEM ESTÁ PEDINDO
    ────────────────────────────────────────────────────────────────
    A Sample Entity não pertence a ninguém, então o controller dela
    não pede `authenticated_customer_key`. Uma transação pertence a um
    cliente, e quase todo método de `TransactionController` exige essa
    chave para decidir o que o pedido pode ver ou fazer.

    Por isso, diferente do sample, estes métodos recebem `Request`: é
    de lá que sai `request.state.customer_key`, o valor que o
    middleware de autenticação (Tarefa 4 do backlog) deve deixar
    pronto depois de validar o token. Enquanto esse middleware não
    existir, `request.state.customer_key` não vai estar populado —
    ajuste a linha marcada abaixo para o nome real que o middleware
    usar.
    """

    @SchemaHandler.validate("post_transaction.json")
    def on_post(self, payload: dict, request: Request) -> JSONResponse:
        # Se o código chegou até aqui, o payload JÁ foi conferido contra
        # o src/schemas/post_transaction.json — inclusive que "amount"
        # é inteiro, nunca float. O resource não checa nada de negócio:
        # ele só chama a regra.
        controller = TransactionController()
        authenticated_customer_key = request.state.customer_key  # populado pelo middleware de auth

        transaction = controller.process_transaction(payload, authenticated_customer_key)

        return JSONResponse(
            content=jsonable_encoder(transaction),
            status_code=http_status.HTTP_201_CREATED,
        )

    def on_get_by_key(self, transaction_key: str, request: Request) -> JSONResponse:
        controller = TransactionController()
        authenticated_customer_key = request.state.customer_key

        transaction = controller.get_by_key(transaction_key, authenticated_customer_key)

        return JSONResponse(
            content=jsonable_encoder(transaction),
            status_code=http_status.HTTP_200_OK,
        )

    @SchemaHandler.validate_query_params("get_transactions.json")
    def on_get_list(self, request: Request) -> JSONResponse:
        """A página pedida, com os filtros que vierem na query string.

        Mesmo mecanismo do `on_get_list` da Sample Entity: o decorator
        já conferiu o FORMATO contra get_transactions.json antes desta
        primeira linha rodar. O que o schema não sabe — se a conta
        filtrada pertence a quem está pedindo — é decidido lá no
        controller, não aqui.

        Nota: o `context.md` do projeto diz que o extrato paginado deve
        viver dentro do `ContaController`/`conta_resource`, não aqui.
        Este endpoint fica como listagem geral de transações (útil
        para outros usos); se a intenção for exclusivamente o extrato
        de uma conta, prefira o endpoint de extrato do Resource de
        Conta e considere remover este método.
        """
        controller = TransactionController()
        authenticated_customer_key = request.state.customer_key

        query_params = request.query_params

        limit = int(query_params.get("limit", DEFAULT_LIMIT))
        page = int(query_params.get("page", DEFAULT_PAGE))

        filters = {
            "origin_account_key": query_params.get("origin_account_key"),
            "destination_account_key": query_params.get("destination_account_key"),
            "type": query_params.get("type"),
            "channel": query_params.get("channel"),
        }

        offset = page * limit
        transactions_page = controller.get_list(limit, offset, filters, authenticated_customer_key)

        # A paginação é assunto do endereço (?limit=&page=), não da
        # transação: por isso quem monta o envelope da página é o
        # resource, e não o DTO — mesma exceção documentada no sample.
        page_envelope = {
            "data": transactions_page["transactions_list"],
            "limit": limit,
            "page": page,
            "is_last_page": transactions_page["is_last_page"],
        }

        return JSONResponse(
            content=jsonable_encoder(page_envelope),
            status_code=http_status.HTTP_200_OK,
        )