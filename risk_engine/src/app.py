from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Risk Engine API", description="Módulo isolado de análise antifraude")

@app.post("/evaluate")
async def evaluate_transaction(request: Request):
    payload = await request.json()
    
    amount = payload.get("amount", 0)
    
    # Regra mockada super simples para testes iniciais
    # Se passar de R$ 50.000,00 (5.000.000 de centavos), nós bloqueamos!
    if amount > 5000000:
        return JSONResponse(status_code=200, content={
            "action": "DENY",
            "reason": "HIGH_AMOUNT_RISK"
        })
        
    return JSONResponse(status_code=200, content={
        "action": "APPROVE"
    })

@app.get("/health_check")
def health_check():
    return JSONResponse(status_code=200, content={"status": "ok"})
