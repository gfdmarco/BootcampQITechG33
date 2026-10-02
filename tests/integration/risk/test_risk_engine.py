from tests.utils import PayloadGenerator, RequestGenerator
import requests
import os
import time

def test_risk_limit_blocks_transaction():
    """
    Test that modifying a user's risk profile to HIGH blocks a transaction
    that exceeds the 1k limit, but allows one below the limit.
    """
    # 1. Create and login customer
    payload = PayloadGenerator.create_customer_payload()
    status, response = RequestGenerator.POST_customer(payload)
    assert status == 201

    customer_key = response["customer_key"]

    login_payload = {
        "document_number": payload["document_number"],
        "password": payload["password"]
    }
    _, login_response = RequestGenerator.POST_auth_login(login_payload)
    access_token = login_response["access_token"]

    # 2. Create account
    status, response = RequestGenerator.POST_customer_account(
        customer_key,
        {"type": "checking"},
        access_token
    )
    assert status == 201
    account_key = response["account_key"]

    # 3. Add balance (10,000 deposits are allowed on LOW or defaults)
    status, _ = RequestGenerator.POST_transaction({
        "account_key": account_key,
        "type": "deposit",
        "amount": 500000 # R$ 5k
    }, access_token)
    assert status == 201

    # 4. Patch Risk Profile directly to HIGH
    RISK_ENGINE_URL = os.getenv("RISK_ENGINE_URL", "http://0.0.0.0:8001")
    INTERNAL_TOKEN = os.getenv("RISK_INTERNAL_TOKEN", "risk_default_token")
    
    # Needs to hit risk engine. The url in docker compose tests is mapped to 8001
    risk_api_host = os.environ.get("SERVER_LOCALHOST", "0.0.0.0")
    risk_api_port = os.environ.get("RISK_API_PORT", "8001")
    risk_url = f"http://{risk_api_host}:{risk_api_port}"

    patch_resp = requests.patch(
        f"{risk_url}/risk_profile/{customer_key}",
        json={"score": "high", "reason": "Integration Test"},
        headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
    )
    # the endpoint is internal, so it might bypass token on options but requires it on others
    # Wait, the app.py requires INTERNAL_TOKEN = os.getenv("INTERNAL_TOKEN", "risk_default_token")
    assert patch_resp.status_code == 200

    # 5. Attempt a transaction > 1k (HIGH limit is 100000 = 1000 reais)
    # We try to transfer 2k
    bob_payload = PayloadGenerator.create_customer_payload()
    _, bob_resp = RequestGenerator.POST_customer(bob_payload)
    bob_key = bob_resp["customer_key"]
    _, bob_login = RequestGenerator.POST_auth_login({
        "document_number": bob_payload["document_number"],
        "password": bob_payload["password"]
    })
    _, bob_acc_resp = RequestGenerator.POST_customer_account(
        bob_key, {"type": "checking"}, bob_login["access_token"]
    )
    bob_account_key = bob_acc_resp["account_key"]

    status, response = RequestGenerator.POST_transaction({
        "origin_account_key": account_key,
        "destination_account_key": bob_account_key,
        "type": "pix",
        "amount": 200000 # R$ 2k > R$ 1k limit
    }, access_token)
    
    # Should be denied because of risk! Wait, the connector raises RiskEngineDenied, which is a 403.
    # custom_errors.py might map RiskEngineDenied to 403 or 422
    assert status == 403 or status == 422
    assert "Risk" in str(response)

    # 6. Attempt a transaction < 1k
    status, response = RequestGenerator.POST_transaction({
        "origin_account_key": account_key,
        "destination_account_key": bob_account_key,
        "type": "pix",
        "amount": 50000 # R$ 500 < R$ 1k limit
    }, access_token)
    assert status == 201
