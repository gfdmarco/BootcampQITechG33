from fastapi import FastAPI, Response, status, Header, HTTPException
from fastapi.responses import JSONResponse

import uuid
import random
import os
import time

app = FastAPI()

EXPECTED_TOKEN = os.environ.get("MOCK_INTERNAL_TOKEN", "default_token")

bank_slips: dict = {}

@app.get("/health_check", status_code=204)
def health_check():
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.post("/bank_slip", status_code=201)
def post_bank_slip(payload: dict, internal_token: str = Header(None, alias = "INTERNAL-TOKEN")):
    if internal_token != EXPECTED_TOKEN:
        raise HTTPException(status_code=403)
    
    bank_slip_key = str(uuid.uuid4())
    amount =  payload.get("amount")
    if not isinstance(amount, int) or amount <= 0:
        raise HTTPException(status_code=400)
    if amount == 666:
        raise HTTPException(status_code=500)
    if amount == 777:
        time.sleep(10)
    barcode = "".join(random.choices("0123456789", k=37)) + str(amount).zfill(10)
    bank_slip = {
        "bank_slip_key": bank_slip_key,
        "amount": payload.get("amount"),
        "barcode": barcode, 
        "expiration_date": payload.get("expiration_date"),
        "payer_data": payload.get("payer_data"),
        "status": "registered"
    }

    bank_slips[bank_slip_key] = bank_slip

    return JSONResponse(content=bank_slip, status_code=status.HTTP_201_CREATED)

@app.get("/bank_slip/{bank_slip_key}", status_code=200)
def get_bank_slip(bank_slip_key: str, internal_token: str = Header(None, alias = "INTERNAL-TOKEN")):
    if internal_token != EXPECTED_TOKEN:
        raise HTTPException(status_code=403)
    
    if bank_slip_key not in bank_slips:
        raise HTTPException(status_code=404)

    return bank_slips[bank_slip_key]