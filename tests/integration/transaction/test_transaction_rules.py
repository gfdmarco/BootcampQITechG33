import threading

from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.api_helpers import (
    balance, deposit, new_customer, open_account, random_key, transfer,
)


def _two_funded_accounts(amount: int):
    """Alice com `amount` na conta e Bob com a conta zerada."""
    alice_key, alice_token, _ = new_customer()
    alice_account = open_account(alice_key, alice_token)
    deposit(alice_account, amount, alice_token)

    bob_key, bob_token, _ = new_customer()
    bob_account = open_account(bob_key, bob_token)

    return alice_account, alice_token, bob_account, bob_token


class TestFeeAgainstBalance:
    def test_fee_pushes_total_above_balance(self):
        """Tópico 5: saldo 1000, TED de 1000 -> tarifa 50, total 1050 -> 422, nada muda."""
        alice_account, alice_token, bob_account, bob_token = _two_funded_accounts(1000)

        status, response = transfer(alice_account, bob_account, 1000, alice_token, channel="ted")

        assert status == 422
        assert response["code"] == "QIT001014"
        assert balance(alice_account, alice_token) == 1000
        assert balance(bob_account, bob_token) == 0

    def test_fee_fits_exactly_in_balance(self):
        """Tópico 5: TED de 952 -> tarifa 47 (47,6 arredondado para baixo), total 999 <= 1000 -> 201."""
        alice_account, alice_token, bob_account, bob_token = _two_funded_accounts(1000)

        status, _ = transfer(alice_account, bob_account, 952, alice_token, channel="ted")

        assert status == 201
        assert balance(alice_account, alice_token) == 1
        assert balance(bob_account, bob_token) == 952


class TestFeesPerChannel:
    def test_pix_has_no_fee(self):
        """Tópico 12: PIX não cobra tarifa."""
        alice_account, alice_token, bob_account, bob_token = _two_funded_accounts(10000)

        status, _ = transfer(alice_account, bob_account, 1000, alice_token, channel="pix")

        assert status == 201
        assert balance(alice_account, alice_token) == 9000
        assert balance(bob_account, bob_token) == 1000

    def test_card_charges_five_percent(self):
        """Tópico 12: cartão cobra 5%: 200 -> tarifa 10. O destino recebe só o valor, sem a tarifa."""
        alice_account, alice_token, bob_account, bob_token = _two_funded_accounts(10000)

        status, _ = transfer(alice_account, bob_account, 200, alice_token, channel="card")

        assert status == 201
        assert balance(alice_account, alice_token) == 10000 - 200 - 10
        assert balance(bob_account, bob_token) == 200

    def test_fee_is_recorded_on_the_transaction(self):
        """A tarifa cobrada fica gravada na transação (fee_amount)."""
        alice_account, alice_token, bob_account, _ = _two_funded_accounts(10000)

        status, response = transfer(alice_account, bob_account, 1000, alice_token, channel="international")
        assert status == 201

        status, statement = RequestGenerator.GET_account_statement(alice_account, None, alice_token)
        assert status == 200
        sent = [t for t in statement["data"] if t["transaction_key"] == response["transaction_key"]]
        assert len(sent) == 1
        assert sent[0]["fee_amount"] == 80
        assert sent[0]["amount"] == 1000


class TestTransferRequiredFields:
    def test_transfer_without_origin(self):
        """Tópico 9: transferência sem origin_account_key -> 422 QIT001021."""
        alice_account, alice_token, bob_account, _ = _two_funded_accounts(1000)

        payload = {"type": "transfer", "destination_account_key": bob_account,
                   "amount": 100, "channel": "pix"}
        status, response = RequestGenerator.POST_transaction(payload, alice_token)

        assert status == 422
        assert response["code"] == "QIT001021"
        assert balance(alice_account, alice_token) == 1000

    def test_invalid_channel(self):
        """Tópico 11: canal fora do enum -> 400 do schema."""
        alice_account, alice_token, bob_account, _ = _two_funded_accounts(1000)

        status, response = transfer(alice_account, bob_account, 100, alice_token, channel="boleto")

        assert status == 400
        assert response["code"] == "QIT000001"
        assert balance(alice_account, alice_token) == 1000

    def test_unknown_field_is_refused(self):
        """additionalProperties: false — campo desconhecido -> 400."""
        alice_account, alice_token, _, _ = _two_funded_accounts(1000)

        payload = PayloadGenerator.deposit(alice_account, 100)
        payload["account_key"] = alice_account
        status, response = RequestGenerator.POST_transaction(payload, alice_token)

        assert status == 400
        assert response["code"] == "QIT000001"


class TestTransferDestination:
    def test_destination_does_not_exist(self):
        """Tópico 10: destino inexistente -> 404 QIT001011, e a origem não perde nada."""
        alice_account, alice_token, _, _ = _two_funded_accounts(1000)

        status, response = transfer(alice_account, random_key(), 100, alice_token)

        assert status == 404
        assert response["code"] == "QIT001011"
        assert balance(alice_account, alice_token) == 1000

    def test_destination_is_blocked(self):
        """Tópico 10: destino bloqueado recusa a transferência, e ninguém perde nem ganha.

        Hoje a API responde 403 (ForbiddenAction). Se vocês criarem um erro
        próprio (ex.: AccountNotActive, 422), troquem o status e o código aqui.
        """
        alice_account, alice_token, bob_account, bob_token = _two_funded_accounts(1000)
        status, _ = RequestGenerator.PUT_account(bob_account, {"status": "blocked"}, bob_token)
        assert status == 200

        status, response = transfer(alice_account, bob_account, 100, alice_token)

        assert status == 403
        assert balance(alice_account, alice_token) == 1000
        assert balance(bob_account, bob_token) == 0


class TestCrossConcurrency:
    def test_simultaneous_transfers_in_both_directions(self):
        """Tópico 15: A->B e B->A ao mesmo tempo, 20 de cada.

        Sem ordem fixa de travas isso gera deadlock (o Postgres mata uma das
        transações e a API devolve 500). Com a ordem por id: nenhum 500, e a
        soma dos dois saldos nunca muda.
        """
        a_key, a_token, _ = new_customer()
        b_key, b_token, _ = new_customer()
        a_account = open_account(a_key, a_token)
        b_account = open_account(b_key, b_token)
        deposit(a_account, 10000, a_token)
        deposit(b_account, 10000, b_token)

        results = []

        def a_to_b():
            results.append(transfer(a_account, b_account, 10, a_token)[0])

        def b_to_a():
            results.append(transfer(b_account, a_account, 10, b_token)[0])

        threads = [threading.Thread(target=fn) for fn in [a_to_b, b_to_a] * 20]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(201) == 40
        assert 500 not in results
        assert balance(a_account, a_token) + balance(b_account, b_token) == 20000