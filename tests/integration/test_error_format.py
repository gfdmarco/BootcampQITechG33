import re


from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.api_helpers import call, new_customer, open_account, transfer

EXPECTED_KEYS = {"title", "description", "translation", "code"}
CODE_FORMAT = re.compile(r"^QIT\d{6}$")


def _assert_error_shape(status: int, body: dict, expected_status: int) -> None:
    assert status == expected_status, body
    assert set(body.keys()) == EXPECTED_KEYS, body
    assert CODE_FORMAT.match(body["code"]), body["code"]
    for key in EXPECTED_KEYS:
        assert isinstance(body[key], str) and body[key].strip(), f"campo {key} vazio"


class TestErrorFormat:
    def test_schema_error_400(self):
        status, body = RequestGenerator.POST_customer({})
        _assert_error_shape(status, body, 400)

    def test_missing_internal_token_403(self):
        status, body = call("GET", "/accounts", internal_token=False)
        _assert_error_shape(status, body, 403)

    def test_missing_jwt_401(self):
        status, body = call("GET", "/accounts")
        _assert_error_shape(status, body, 401)

    def test_wrong_credentials_401(self):
        payload = PayloadGenerator.create_customer_payload()
        status, body = RequestGenerator.POST_auth_login({
            "document_number": payload["document_number"], "password": "SenhaErrada123",
        })
        _assert_error_shape(status, body, 401)

    def test_forbidden_403(self):
        alice_key, alice_token, _ = new_customer()
        alice_account = open_account(alice_key, alice_token)
        _, bob_token, _ = new_customer()

        status, body = RequestGenerator.GET_account(alice_account, bob_token)
        _assert_error_shape(status, body, 403)

    def test_not_found_404(self):
        _, token, _ = new_customer()
        status, body = RequestGenerator.GET_account("00000000-0000-4000-8000-000000000000", token)
        _assert_error_shape(status, body, 404)

    def test_method_not_allowed_405(self):
        status, body = call("PUT", "/health_check")
        _assert_error_shape(status, body, 405)

    def test_conflict_409(self):
        first = PayloadGenerator.create_customer_payload()
        assert RequestGenerator.POST_customer(first)[0] == 201
        second = PayloadGenerator.create_customer_payload(document_number=first["document_number"])

        status, body = RequestGenerator.POST_customer(second)
        _assert_error_shape(status, body, 409)

    def test_business_rule_422(self):
        alice_key, alice_token, _ = new_customer()
        alice_account = open_account(alice_key, alice_token)
        bob_key, bob_token, _ = new_customer()
        bob_account = open_account(bob_key, bob_token)

        status, body = transfer(alice_account, bob_account, 100, alice_token)
        _assert_error_shape(status, body, 422)

    def test_error_never_leaks_internals(self):
        """Nenhum erro expõe stack trace, SQL ou id interno."""
        _, token, _ = new_customer()
        status, body = RequestGenerator.GET_account("00000000-0000-4000-8000-000000000000", token)

        text = " ".join(body.values()).lower()
        for leak in ("traceback", "sqlalchemy", "select ", "psycopg", "customer_id", "account_id"):
            assert leak not in text, leak