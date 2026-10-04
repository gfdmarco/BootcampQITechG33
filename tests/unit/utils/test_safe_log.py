"""O log de retorno nunca leva dado sensível (src/utils/safe_log.py)."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from utils.safe_log import format_fields, mask_cpf, mask_email, masked_query, sanitize


def test_cpf_keeps_only_the_first_three_digits():
    assert mask_cpf("123.456.789-09") == "123.***.***-**"


def test_email_keeps_first_letter_and_domain():
    assert mask_email("gabriel@unicamp.br") == "g***@unicamp.br"


def test_passwords_never_appear_not_even_hashed():
    clean = sanitize({"password": "Senha123", "password_hash": "$2b$12$abc",
                      "current_password": "a", "new_password": "b", "name": "Ana"})
    assert clean == {"name": "Ana"}


def test_tokens_and_balance_are_hidden():
    clean = sanitize({"access_token": "eyJ...", "refresh_token": "eyJ...", "balance": 5000})
    assert clean == {"access_token": "<emitido>", "refresh_token": "<emitido>", "balance": "<oculto>"}


def test_nested_and_lists():
    line = format_fields({
        "customer_key": "k1",
        "document_number": "123.456.789-09",
        "email": "ana@x.com",
        "status_events": [{"a": 1}, {"a": 2}],
        "owner": {"cnpj": "12345678000199"},
    })
    assert "123.456.789-09" not in line
    assert "123.***.***-**" in line
    assert "a***@x.com" in line
    assert "status_events=<2 itens>" in line
    assert "cnpj=123***********" in line


def test_query_string_is_masked_for_the_request_log():
    from starlette.datastructures import QueryParams

    line = masked_query(QueryParams("document_number=123.456.789-09&limit=10&email=ana@x.com"))
    assert line == "document_number=123.***.***-**&limit=10&email=a***@x.com"

@pytest.mark.filterwarnings("ignore::sqlalchemy.exc.MovedIn20Warning")
def test_return_log_reports_the_password_outcome_never_the_password(monkeypatch):
    """Os controllers registram a senha só pelo resultado: `password=created`."""
    import constants
    # importar o controller cria o engine do SQLAlchemy; ele só precisa de uma URL, nada conecta
    monkeypatch.setattr(constants, "DATABASE_URL", constants.DATABASE_URL or "postgresql://unit:unit@localhost/unit")
    from controllers.base_controller import BaseController

    lines = []

    class _Capture:
        def info(self, message):
            lines.append(message)

    controller = BaseController.__new__(BaseController)   # sem abrir sessão de banco
    controller.logger = _Capture()
    controller._log_return(
        "Cliente registrado",
        {"customer_key": "k1", "document_number": "123.456.789-09", "password": "Senha123"},
        password="created",
    )

    assert lines == ["RETORNO Cliente registrado | customer_key=k1 document_number=123.***.***-** password=created"]
    assert "Senha123" not in lines[0]
