from datetime import date
from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator


def birthdate_for_age(age_in_years: int) -> str:
    today = date.today()
    if today.month == 2 and today.day == 29:
        return date(today.year - age_in_years, 2, 28).isoformat()
    return date(today.year - age_in_years, today.month, today.day).isoformat()


class TestCustomerCreate:
    def test_creates_customer_successfully(self):
        document_number = RandomGenerator.generate_cpf()
        payload = PayloadGenerator.create_customer_payload()
        payload["document_number"] = document_number

        status, response = RequestGenerator.POST_customer(payload)
        
        assert status == 201
        assert "customer_key" in response
        assert response["name"] == payload["name"]
        assert response["email"] == payload["email"]
        assert response["document_number"] == document_number
        assert response["status"] == "created"
        
        # A senha não pode ser retornada!
        assert "password" not in response
        assert "password_hash" not in response

    def test_refuses_underage_customer(self):
        payload = PayloadGenerator.create_customer_payload()
        payload["birthdate"] = birthdate_for_age(17)

        status, response = RequestGenerator.POST_customer(payload)

        assert status == 422
        assert response["code"] == "QIT001008"

    def test_refuses_weak_password(self):
        payload = PayloadGenerator.create_customer_payload()
        payload["password"] = "fraca1"  # Só 6 caracteres, mínimo é 8
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 400

        payload["password"] = "somenteletras"  # Falta número
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 400

        payload["password"] = "123456789"  # Falta letra
        status, response = RequestGenerator.POST_customer(payload)
        assert status == 400

    def test_refuses_duplicated_document_number(self):
        primeira = PayloadGenerator.create_customer_payload()
        status, _ = RequestGenerator.POST_customer(primeira)
        assert status == 201

        segunda = PayloadGenerator.create_customer_payload()
        segunda["document_number"] = primeira["document_number"]

        status, response = RequestGenerator.POST_customer(segunda)

        assert status == 409
        assert response["code"] == "QIT001004"

    def test_refuses_duplicated_email(self):
        primeira = PayloadGenerator.create_customer_payload()
        status, _ = RequestGenerator.POST_customer(primeira)
        assert status == 201

        segunda = PayloadGenerator.create_customer_payload()
        segunda["email"] = primeira["email"]

        status, response = RequestGenerator.POST_customer(segunda)

        assert status == 409
        assert response["code"] == "QIT001005"
