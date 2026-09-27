import threading

from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.api_helpers import balance, deposit, new_customer, open_account, transfer


class TestTransactionEndpoints:
    def test_deposit(self):
        """POST /transactions depósito. Saldo sobe exatamente o valor. Conta de outro, conta bloqueada, amount 0, -5, "100", 100.5 -> recusar"""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)

        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)

        # Alice deposita 100 na própria conta
        status, response = RequestGenerator.POST_transaction(PayloadGenerator.deposit(alice_acc, 100), alice_token)
        assert status == 201
        assert "transaction_key" in response
        assert balance(alice_acc, alice_token) == 100

        # Alice tenta depositar na conta do Bob -> 403, e o saldo do Bob não muda
        status, response = RequestGenerator.POST_transaction(PayloadGenerator.deposit(bob_acc, 100), alice_token)
        assert status == 403
        assert response["code"] == "QIT002003"
        assert balance(bob_acc, bob_token) == 0

        # Valores inválidos são barrados pelo schema -> 400, e o saldo não muda
        for invalid_amount in [0, -5, "100", 100.5]:
            status, response = RequestGenerator.POST_transaction(
                PayloadGenerator.deposit(alice_acc, invalid_amount), alice_token
            )
            assert status == 400, invalid_amount
            assert response["code"] == "QIT000001"
        assert balance(alice_acc, alice_token) == 100

        # Conta bloqueada não recebe depósito
        status, _ = RequestGenerator.PUT_account(alice_acc, {"status": "blocked"}, alice_token)
        assert status == 200
        status, _ = RequestGenerator.POST_transaction(PayloadGenerator.deposit(alice_acc, 100), alice_token)
        assert status == 403

    def test_transfer(self):
        """POST /transactions transferência. Origem = antes - valor - tarifa; destino = antes + valor."""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)

        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)

        deposit(alice_acc, 1000, alice_token)

        # Alice -> Bob via PIX (tarifa 0)
        status, _ = transfer(alice_acc, bob_acc, 100, alice_token, channel="pix")
        assert status == 201
        assert balance(alice_acc, alice_token) == 900
        assert balance(bob_acc, bob_token) == 100

        # Sem saldo -> 422, e os saldos continuam intactos
        status, response = transfer(alice_acc, bob_acc, 901, alice_token)
        assert status == 422
        assert response["code"] == "QIT001014"
        assert balance(alice_acc, alice_token) == 900
        assert balance(bob_acc, bob_token) == 100

        # Alice tenta transferir DA conta do Bob -> 403
        status, response = transfer(bob_acc, alice_acc, 50, alice_token)
        assert status == 403
        assert response["code"] == "QIT002003"
        assert balance(bob_acc, bob_token) == 100

        # Mesma conta na origem e no destino -> 400
        status, response = transfer(alice_acc, alice_acc, 50, alice_token)
        assert status == 400
        assert balance(alice_acc, alice_token) == 900

    def test_concurrency(self):
        """Concorrência: 20 transferências simultâneas de 100 com saldo 1.000: exatamente 10 aceitas, e aceitas * 100 + saldo final = 1.000"""
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)

        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)

        deposit(alice_acc, 1000, alice_token)

        results = []

        def send_100():
            results.append(transfer(alice_acc, bob_acc, 100, alice_token, channel="pix")[0])

        threads = [threading.Thread(target=send_100) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        accepted = results.count(201)
        assert accepted == 10
        assert results.count(422) == 10
        assert balance(alice_acc, alice_token) == 0
        assert balance(bob_acc, bob_token) == 1000