from tests.utils.api_helpers import balance, deposit, new_customer, open_account, transfer


class TestTransactionFees:
    def test_fees(self):
        """Tarifa: TED 5% e internacional 8%, arredondada para baixo (a favor do cliente).

        Valores em centavos: 199 = R$ 1,99.
        """
        alice_key, alice_token, _ = new_customer()
        alice_acc = open_account(alice_key, alice_token)

        bob_key, bob_token, _ = new_customer()
        bob_acc = open_account(bob_key, bob_token)

        deposit(alice_acc, 10000, alice_token)

        # TED 5%: 199 * 5% = 9,95 -> 9 centavos
        status, _ = transfer(alice_acc, bob_acc, 199, alice_token, channel="ted")
        assert status == 201
        assert balance(alice_acc, alice_token) == 10000 - 199 - 9  # 9792

        # Internacional 8%: 100 * 8% = 8
        status, _ = transfer(alice_acc, bob_acc, 100, alice_token, channel="international")
        assert status == 201
        assert balance(alice_acc, alice_token) == 9792 - 100 - 8  # 9684

        # O destino recebe só o valor, nunca a tarifa
        assert balance(bob_acc, bob_token) == 199 + 100