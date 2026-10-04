"""Ferramentas de idempotência: o mesmo pedido, um efeito só.

Três peças, cada uma num lugar (padrão do slide 29 do Dia 4):
  • a BUSCA mora no repository (`get_by_idempotency_key`);
  • a DECISÃO mora no controller (`existing` → devolve o original, ou
    409 se a chave voltou com outro pedido);
  • a GARANTIA mora no banco (UNIQUE na coluna da chave).

Entre a busca e a gravação existe uma janela: dois pedidos simultâneos
com a mesma chave podiam os dois ver "não existe" e os dois executar.
O `lock_idempotency_key` fecha essa janela com um advisory lock do
Postgres: o segundo pedido espera o primeiro terminar (commit ou
rollback) e só então faz a busca — e aí encontra o `existing`.
"""
import hashlib
import re

from sqlalchemy import text

from errors import MissingIdempotencyKey

IDEMPOTENCY_HEADER = "Idempotency-Key"

_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def read_idempotency_key(request) -> str:
    """Lê o header Idempotency-Key, obrigatório e no formato UUID.

    A chave é gerada por QUEM CHAMA, uma por operação: é ela que diz
    "este pedido é a repetição daquele". Sem chave, não há como separar
    um retry de uma segunda operação legítima de mesmo valor.
    """
    key = request.headers.get(IDEMPOTENCY_HEADER)
    if key is None or not _UUID_PATTERN.match(key.strip()):
        raise MissingIdempotencyKey()
    return key.strip().lower()


def customer_idempotency_key(document_number: str) -> str:
    """A chave do cadastro de cliente: derivada do CPF, gerada pelo servidor.

    O CPF é único por pessoa, então dois cadastros com o mesmo CPF SÃO o
    mesmo pedido — não precisa o cliente inventar uma chave. Guardamos o
    SHA-256 dos dígitos (com prefixo de domínio), nunca o CPF em texto.
    """
    digits = re.sub(r"\D", "", document_number)
    return hashlib.sha256(f"customer:{digits}".encode("utf-8")).hexdigest()


def lock_idempotency_key(session, scope: str, key: str) -> None:
    """Trava a chave até o fim da transação do banco (commit ou rollback).

    `pg_advisory_xact_lock` não trava linha nenhuma: trava um NÚMERO.
    Dois pedidos com a mesma chave pedem o mesmo número; o segundo fica
    esperando. Pedidos com chaves diferentes não esperam ninguém.
    """
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
        {"lock_name": f"{scope}:{key}"},
    )
