"""A tesouraria nunca loga — nem com a senha certa.

A primeira trava é a senha desconhecida (o hash no database.sql é de um
segredo jogado fora). Este teste prova a segunda: trocamos o hash por um
de senha CONHECIDA, como faria alguém com acesso ao banco, e o login
continua recusado.
"""
from passlib.hash import bcrypt
from sqlalchemy import create_engine, text

from tests.utils import RequestGenerator
from tests.utils.db_utils import DbUtils

BANK_CUSTOMER_KEY = "00000000-0000-4000-8000-000000000001"
BANK_CPF = "000.000.000-00"


def test_treasury_cannot_log_in_even_with_the_right_password():
    engine = create_engine(DbUtils.database_url())
    with engine.begin() as conn:
        original = conn.execute(
            text("SELECT password_hash FROM customer WHERE customer_key = :k"), {"k": BANK_CUSTOMER_KEY}
        ).scalar_one()
        conn.execute(
            text("UPDATE customer SET password_hash = :h WHERE customer_key = :k"),
            {"h": bcrypt.hash("SenhaConhecida1"), "k": BANK_CUSTOMER_KEY},
        )
    try:
        status, body = RequestGenerator.POST_auth_login(
            {"document_number": BANK_CPF, "password": "SenhaConhecida1"})

        assert status == 401
        assert body["code"] == "QIT002001"          # mesma resposta de senha errada
    finally:
        with engine.begin() as conn:
            conn.execute(text("UPDATE customer SET password_hash = :h WHERE customer_key = :k"),
                         {"h": original, "k": BANK_CUSTOMER_KEY})
        engine.dispose()
