from uuid import uuid4

from tests.utils.random_generator import RandomGenerator


class PayloadGenerator:
    @staticmethod
    def create_new_status_payload(new_status: str = None) -> dict:
        payload = {"status": new_status}
        return payload

    @staticmethod
    def create_customer_payload(
        name: str = None,
        email: str = None,
        document_number: str = None,
        birthdate: str = None,
        password: str = None,
    ) -> dict:
        if name is None:
            name = "Joao Gabriel"

        if email is None:
            email = f"joao.gabriel.{uuid4()}@exemplo.com.br"

        if document_number is None:
            document_number = RandomGenerator.generate_cpf()

        if birthdate is None:
            birthdate = "1990-05-17"

        if password is None:
            password = "SecurePassword123"

        payload = {
            "name": name,
            "email": email,
            "document_number": document_number,
            "birthdate": birthdate,
            "password": password,
        }
        return payload

    @staticmethod
    def deposit(account_key: str, amount: int, channel: str = "pix") -> dict:
        return {"type": "deposit", "destination_account_key": account_key,
                "amount": amount, "channel": channel}

    @staticmethod
    def transfer(origin: str, destination: str, amount: int, channel: str = "pix") -> dict:
        return {"type": "transfer", "origin_account_key": origin,
                "destination_account_key": destination, "amount": amount, "channel": channel}
