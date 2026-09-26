import secrets

def check_digit(digits: str) -> str:
    "Lógica baseada no módulo 11, similar ao CPF"
    total, weight = 0,2
    for d in reversed(digits):
        total += int(d) * weight 
        weight = 2 if weight == 9 else weight + 1
    dv = 11 - (total % 11)
    return "0" if dv >= 10 else str(dv)

def generate_account_number() -> str:
    base = f"{secrets.randbelow(10**8):08d}"
    return f"{base}-{check_digit(base)}"