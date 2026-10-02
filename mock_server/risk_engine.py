from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

@app.get("/risk_profile/{customer_key}")
def get_risk_profile(customer_key: str, internal_token: str = Header(None, alias="INTERNAL-TOKEN")):
    if internal_token != "risk_default_token":
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Predictable behavior based on prefix
    if customer_key.startswith("high"):
        return {"customer_key": customer_key, "score": "high"}
    elif customer_key.startswith("med"):
        return {"customer_key": customer_key, "score": "medium"}
    elif customer_key.startswith("unk"):
        return {"customer_key": customer_key, "score": "unknown"}
    return {"customer_key": customer_key, "score": "low"}
