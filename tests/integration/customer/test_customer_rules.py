from tests.utils import PayloadGenerator, RandomGenerator, RequestGenerator
from tests.utils.api_helpers import deposit, new_customer, open_account, transfer


def _cpf_with_wrong_check_digit() -> str:
    """Um CPF com o formato certo e o último dígito trocado."""
    valid = RandomGenerator.generate_cpf()
    last = int(valid[-1])
    return valid[:-1] + str((last + 1) % 10)


class TestCustomerDataValidation:
    def test_refuses_cpf_with_wrong_check_digit(self):
        """Tópico 7: formato certo, dígito verificador errado -> 422 QIT001003."""
        payload = PayloadGenerator.create_customer_payload(document_number=_cpf_with_wrong_check_digit())

        status, response = RequestGenerator.POST_customer(payload)

        assert status == 422
        assert response["code"] == "QIT001003"

    def test_refuses_birthdate_that_does_not_exist(self):
        """Tópico 8: 30 de fevereiro passa no regex, mas não existe -> 422 QIT001009."""
        payload = PayloadGenerator.create_customer_payload(birthdate="2000-02-30")

        status, response = RequestGenerator.POST_customer(payload)

        assert status == 422
        assert response["code"] == "QIT001009"


class TestCustomerDeleteRules:
    def test_refuses_delete_while_an_account_has_balance(self):
        """Tópico 1: cliente com saldo não pode se excluir -> 409 QIT001023, e nada muda."""
        customer_key, token, payload = new_customer()
        account_key = open_account(customer_key, token)
        deposit(account_key, 500, token)

        status, response = RequestGenerator.DELETE_customer(customer_key, token)

        assert status == 409
        assert response["code"] == "QIT001023"

        # o cadastro continua ativo: login funciona e a conta segue aberta com o saldo
        status, _ = RequestGenerator.POST_auth_login({
            "document_number": payload["document_number"],
            "password": payload["password"],
        })
        assert status == 200

        status, account = RequestGenerator.GET_account(account_key, token)
        assert status == 200
        assert account["status"] == "active"
        assert account["balance"] == 500

    def test_delete_closes_every_account_of_the_customer(self):
        """Tópico 2: delete sem saldo encerra as contas; ninguém consegue mais mandar dinheiro pra elas."""
        customer_key, token, _ = new_customer()
        checking = open_account(customer_key, token, "checking")
        savings = open_account(customer_key, token, "savings")

        status, _ = RequestGenerator.DELETE_customer(customer_key, token)
        assert status == 204

        # o token ainda vale por alguns minutos: dá pra conferir que as contas estão encerradas
        for account_key in (checking, savings):
            status, account = RequestGenerator.GET_account(account_key, token)
            assert status == 200
            assert account["status"] == "closed"

        # outro cliente tenta transferir para a conta encerrada -> recusado
        other_key, other_token, _ = new_customer()
        other_account = open_account(other_key, other_token)
        deposit(other_account, 1000, other_token)

        status, _ = transfer(other_account, checking, 100, other_token)
        assert status == 403

        # e o dinheiro do outro cliente não saiu
        status, other = RequestGenerator.GET_account(other_account, other_token)
        assert other["balance"] == 1000

    def test_delete_is_idempotent(self):
        """Pedir o delete duas vezes não é erro: a segunda também responde 204."""
        customer_key, token, _ = new_customer()

        status, _ = RequestGenerator.DELETE_customer(customer_key, token)
        assert status == 204

        status, _ = RequestGenerator.DELETE_customer(customer_key, token)
        assert status == 204

    def test_deleted_customer_cannot_move_money_with_a_token_still_valid(self):
        """Tópico 16: o access token ainda não expirou, mas o cliente excluído não transaciona."""
        customer_key, token, _ = new_customer()
        account_key = open_account(customer_key, token)

        status, _ = RequestGenerator.DELETE_customer(customer_key, token)
        assert status == 204

        status, response = RequestGenerator.POST_transaction(
            PayloadGenerator.deposit(account_key, 100), token
        )
        assert status == 403
        assert response["code"] == "QIT002003"

        # e também não abre conta nova
        status, _ = RequestGenerator.POST_customer_account(customer_key, {"type": "checking"}, token)
        assert status == 403