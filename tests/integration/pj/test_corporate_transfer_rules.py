"""Regras de transferência PJ que os testes originais não cobriam.

O teste original só conferia que a aprovação devolve status "approved".
Aqui o que se confere é o DINHEIRO: quanto saiu, quanto entrou, quantas vezes.
"""
import threading

from tests.utils import PayloadGenerator, RequestGenerator
from tests.utils.api_helpers import balance, call, new_customer, open_account
from tests.utils.random_generator import RandomGenerator

INITIAL_BALANCE = 5000


def _cnpj() -> str:
    return RandomGenerator.generate_cnpj().replace(".", "").replace("/", "").replace("-", "")


def corporate_scenario():
    """Empresa com owner, finance, operator e viewer, conta PJ com R$ 50,00 e um destino."""
    owner_key, owner_token, _ = new_customer()
    members = {}
    for role in ("finance", "operator", "viewer"):
        key, token, _ = new_customer()
        members[role] = (key, token)

    status, corp = call("POST", "/corporates", owner_token, payload={"cnpj": _cnpj(), "company_name": "Rules Corp"})
    assert status == 201, corp
    corp_key = corp["corporate_key"]

    for role, (key, _) in members.items():
        status, body = call("POST", f"/corporates/{corp_key}/members", owner_token,
                            payload={"customer_key": key, "role": role})
        assert status in (200, 201), body

    finance_token = members["finance"][1]
    status, acc = call("POST", f"/corporates/{corp_key}/accounts", finance_token)
    assert status in (200, 201), acc
    corp_account = acc["account_key"]

    status, body = RequestGenerator.POST_transaction(PayloadGenerator.deposit(corp_account, INITIAL_BALANCE), finance_token)
    assert status == 201, body

    target_key, target_token, _ = new_customer()
    target_account = open_account(target_key, target_token)

    return {
        "corp_key": corp_key,
        "corp_account": corp_account,
        "target_account": target_account,
        "target_token": target_token,
        "owner": owner_token,
        "finance": finance_token,
        "operator": members["operator"][1],
        "viewer": members["viewer"][1],
    }


def request_transfer(env, token, amount, origin=None):
    return call("POST", f"/corporates/{env['corp_key']}/transfers", token, payload={
        "origin_account_key": origin or env["corp_account"],
        "destination_account_key": env["target_account"],
        "amount": amount,
    })


def approve(env, request_id, token):
    return call("POST", f"/corporates/{env['corp_key']}/transfers/{request_id}/approve", token)


class TestCorporateTransferMoney:
    def test_request_alone_does_not_move_money(self):
        env = corporate_scenario()

        status, req = request_transfer(env, env["operator"], 1000)

        assert status in (200, 201), req
        assert req["status"] == "pending"
        assert balance(env["corp_account"], env["finance"]) == INITIAL_BALANCE
        assert balance(env["target_account"], env["target_token"]) == 0

    def test_approval_moves_the_money_once(self):
        env = corporate_scenario()
        _, req = request_transfer(env, env["operator"], 1000)

        status, body = approve(env, req["request_id"], env["finance"])

        assert status == 200, body
        assert balance(env["corp_account"], env["finance"]) == INITIAL_BALANCE - 1000   # pix: sem tarifa
        assert balance(env["target_account"], env["target_token"]) == 1000

    def test_approving_twice_moves_money_once(self):
        env = corporate_scenario()
        _, req = request_transfer(env, env["operator"], 1000)

        assert approve(env, req["request_id"], env["finance"])[0] == 200
        status, _ = approve(env, req["request_id"], env["owner"])

        assert status in (403, 409)
        assert balance(env["target_account"], env["target_token"]) == 1000

    def test_simultaneous_approvals_move_money_once(self):
        """Owner e finance clicam em aprovar ao mesmo tempo: a transferência acontece uma vez."""
        env = corporate_scenario()
        _, req = request_transfer(env, env["operator"], 1000)

        results = []
        threads = [threading.Thread(target=lambda t=tok: results.append(approve(env, req["request_id"], t)[0]))
                   for tok in [env["finance"], env["owner"]] * 3]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count(200) == 1, results
        assert balance(env["target_account"], env["target_token"]) == 1000
        assert balance(env["corp_account"], env["finance"]) == INITIAL_BALANCE - 1000

    def test_approval_without_balance_fails_and_nothing_moves(self):
        env = corporate_scenario()
        _, req = request_transfer(env, env["operator"], INITIAL_BALANCE + 1)

        status, _ = approve(env, req["request_id"], env["finance"])

        assert status == 422
        assert balance(env["corp_account"], env["finance"]) == INITIAL_BALANCE
        assert balance(env["target_account"], env["target_token"]) == 0


class TestCorporateTransferAccess:
    def test_outsider_cannot_request(self):
        env = corporate_scenario()
        _, outsider_token, _ = new_customer()

        status, _ = request_transfer(env, outsider_token, 1000)

        assert status == 403

    def test_viewer_cannot_approve(self):
        env = corporate_scenario()
        _, req = request_transfer(env, env["operator"], 1000)

        status, _ = approve(env, req["request_id"], env["viewer"])

        assert status == 403
        assert balance(env["target_account"], env["target_token"]) == 0

    def test_cannot_use_a_personal_account_as_origin(self):
        """A conta pessoal do operador não é da empresa: não pode ser origem de transferência PJ."""
        env = corporate_scenario()
        op_key, op_token, _ = new_customer()
        personal = open_account(op_key, op_token)

        status, _ = request_transfer(env, env["operator"], 1000, origin=personal)

        assert status in (403, 422)

    def test_unknown_request_is_404(self):
        env = corporate_scenario()

        status, _ = approve(env, 999999, env["finance"])

        assert status == 404

    def test_refuses_invalid_amount(self):
        env = corporate_scenario()

        for amount in [0, -1, "100", 10.5]:
            status, _ = request_transfer(env, env["operator"], amount)
            assert status == 400, amount