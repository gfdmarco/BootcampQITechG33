"""Cliente inexistente na gestão de membros da PJ dá 404, não 500.

O controller chamava NotFoundCustomer() sem a chave que a exceção exige;
o Python estourava TypeError antes de o erro virar resposta, e a API
devolvia 500.
"""
from uuid import uuid4

from tests.utils.api_helpers import call, new_customer
from tests.utils.random_generator import RandomGenerator


def corporate_with_owner():
    owner_key, owner_token, _ = new_customer()
    cnpj = RandomGenerator.generate_cnpj().replace(".", "").replace("/", "").replace("-", "")
    status, corp = call("POST", "/corporates", owner_token, payload={"cnpj": cnpj, "company_name": "Membros Ltda"})
    assert status == 201, corp
    return corp["corporate_key"], owner_token


class TestUnknownCustomerInCorporate:
    def test_adding_unknown_customer_is_404(self):
        corp_key, owner_token = corporate_with_owner()
        ghost = str(uuid4())

        status, body = call("POST", f"/corporates/{corp_key}/members", owner_token,
                            payload={"customer_key": ghost, "role": "viewer"})

        assert status == 404, body
        assert body["code"] == "QIT001012"
        assert ghost in body["description"]

    def test_removing_unknown_customer_is_404(self):
        corp_key, owner_token = corporate_with_owner()

        status, body = call("DELETE", f"/corporates/{corp_key}/members/{uuid4()}", owner_token)

        assert status == 404, body
        assert body["code"] == "QIT001012"

    def test_removing_customer_that_is_not_a_member_is_404(self):
        corp_key, owner_token = corporate_with_owner()
        outsider_key, _, _ = new_customer()

        status, body = call("DELETE", f"/corporates/{corp_key}/members/{outsider_key}", owner_token)

        assert status == 404, body
        assert body["code"] == "QIT001012"
