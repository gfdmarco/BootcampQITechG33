"""Log de retorno sem dado sensível.

O middleware de log escreve ENTROU e SAIU de toda requisição, mas não
diz O QUE aconteceu. Os controllers, antes de cada return, chamam
`BaseController._log_return(...)`, que escreve uma linha como:

    RETORNO Cliente registrado | customer_key=7f3c... document_number=123.***.***-** email=g***@unicamp.br senha=criada

e passa tudo por `sanitize` antes. As regras:

  • CPF e CNPJ saem só com os 3 primeiros dígitos; o resto vira "*".
  • E-mail sai com a primeira letra do usuário e o domínio.
  • Senha nunca sai — nem em texto, nem em hash. Quem chama descreve o
    resultado ("senha=criada", "senha=conferida", "senha=alterada").
  • Tokens (access/refresh) nunca saem: viram "<emitido>".
  • Saldo não sai: vira "<oculto>".
  • Listas não são despejadas no log: sai só a quantidade de itens.
"""

_CPF_KEYS = {"document_number", "cpf"}
_CNPJ_KEYS = {"cnpj"}
_EMAIL_KEYS = {"email"}
_DROP_KEYS = {"password", "password_hash", "current_password", "new_password"}
_TOKEN_KEYS = {"access_token", "refresh_token"}
_HIDDEN_KEYS = {"balance"}   # saldo é dado financeiro do cliente: não vai para o log


def _mask_digits(value: str, visible: int = 3) -> str:
    """Mantém os `visible` primeiros dígitos e troca os outros por '*',
    preservando a pontuação: 123.456.789-09 → 123.***.***-**."""
    out, seen = [], 0
    for char in str(value):
        if char.isdigit():
            seen += 1
            out.append(char if seen <= visible else "*")
        else:
            out.append(char)
    return "".join(out)


def mask_cpf(value) -> str:
    return _mask_digits(value, visible=3) if value else value


def mask_cnpj(value) -> str:
    return _mask_digits(value, visible=3) if value else value


def mask_email(value) -> str:
    if not value or "@" not in str(value):
        return value
    user, domain = str(value).split("@", 1)
    return f"{user[:1]}***@{domain}"


def sanitize(data):
    """Copia `data` trocando o que é sensível pela versão mascarada."""
    if isinstance(data, dict):
        clean = {}
        for key, value in data.items():
            lower = str(key).lower()
            if lower in _DROP_KEYS:
                continue
            if lower in _TOKEN_KEYS:
                clean[key] = "<emitido>"
            elif lower in _HIDDEN_KEYS:
                clean[key] = "<oculto>"
            elif lower in _CPF_KEYS:
                clean[key] = mask_cpf(value)
            elif lower in _CNPJ_KEYS:
                clean[key] = mask_cnpj(value)
            elif lower in _EMAIL_KEYS:
                clean[key] = mask_email(value)
            elif isinstance(value, (list, tuple)):
                clean[key] = f"<{len(value)} itens>"
            elif isinstance(value, dict):
                clean[key] = sanitize(value)
            else:
                clean[key] = value
        return clean
    if isinstance(data, (list, tuple)):
        return f"<{len(data)} itens>"
    return data


def format_fields(data) -> str:
    """Achata o dicionário já limpo em 'chave=valor chave=valor'."""
    clean = sanitize(data)
    if not isinstance(clean, dict):
        return str(clean)
    parts = []
    for key, value in clean.items():
        if isinstance(value, dict):
            value = "{" + format_fields(value) + "}"
        parts.append(f"{key}={value}")
    return " ".join(parts)


def masked_query(query_params) -> str:
    """A query string para o log, com CPF/CNPJ/e-mail mascarados.

    Ex.: GET /customers?document_number=123.456.789-09 sai no log como
    document_number=123.***.***-**. Os outros parâmetros saem como vieram.
    """
    parts = []
    for key, value in query_params.multi_items():
        clean = sanitize({key: value}).get(key, "")
        parts.append(f"{key}={clean}")
    return "&".join(parts)
