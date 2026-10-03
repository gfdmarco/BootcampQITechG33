"""O relógio do banco.

O banco opera no horário de Brasília: "hoje", para o vencimento de um
boleto ou para a idade de um cliente, é o hoje de Brasília — não o do
servidor. O container Docker roda em UTC, que está 3 horas à frente: das
21h à meia-noite, `date.today()` lá dentro já devolve o dia seguinte, e o
boleto emitido às 22h vence um dia depois do que deveria.

Toda regra de negócio que depende de data usa as funções daqui, nunca
`date.today()` ou `datetime.now()` direto.

O fuso vem do pacote `tzdata` (requirements.txt), que traz a base de fusos
junto com o Python — a imagem slim do Docker não garante tê-la.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

BUSINESS_TZ = ZoneInfo("America/Sao_Paulo")


def business_today() -> date:
    """A data de hoje em Brasília."""
    return datetime.now(BUSINESS_TZ).date()


def business_now() -> datetime:
    """Agora, em Brasília, sem fuso anexado (as colunas do banco são
    TIMESTAMP sem fuso)."""
    return datetime.now(BUSINESS_TZ).replace(tzinfo=None)
