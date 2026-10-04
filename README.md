# Bootcamp QI Tech 2026 — Core bancário (G33)

API REST de um banco digital, em **Python + FastAPI + PostgreSQL**, rodando em **Docker Compose**.

O que o projeto oferece:
- **Pessoa física:** cadastro, login com JWT, até 5 contas e extrato.
- **Movimentação:** depósito e transferência por PIX, TED, cartão e internacional, com tarifa.
- **Boleto de depósito**, emitido por um provedor externo (simulado).
- **Empréstimo** com parcelas.
- **Pessoa jurídica:** membros com papéis e transferência só com aprovação.
- **Notificações.**
- **Motor de Risco** separado, com classificação de score por LLM.

O desenho, as decisões e o que foi descartado estão na RFC: **[`docs/rfc_prototipo_bancario.pdf`](docs/rfc_prototipo_bancario.pdf)**. A versão editável é a [`.md`](docs/rfc_prototipo_bancario.md).

## Como rodar

O passo a passo completo, com portas, chamadas de exemplo e logs, está no **anexo "Como rodar o projeto" da RFC**. O resumo:

```bash
cp .env.example .env               # os valores padrão funcionam com o compose
docker compose up -d --build       # sobe os 7 serviços
docker compose ps                  # espere ficarem (healthy); o risk_worker aparece só como Up

python3 -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
pytest -q tests
```

Se o schema do banco mudar (`database/database.sql`), recrie os volumes com `docker compose down -v && docker compose up -d --build`.

## Serviços

| Serviço | Porta | Papel |
|---|---|---|
| `api` | 3000 | Core bancário |
| `db` | 5432 | PostgreSQL do Core |
| `bankslip-mock` | 8080 | Provedor de boletos simulado |
| `risk_engine` · `db_risk` | 8001 · 5433 | Motor de Risco e o banco dele |
| `risk_worker` | — | Worker LLM: reclassifica o score a cada 6 h (opcional: `GROQ_API_KEY` no `.env`) |
| `redis` | 6379 | Cache do Motor de Risco |

## Garantias que o desenho dá

- Dinheiro sempre em **centavos inteiros**. O saldo muda por `UPDATE` condicional no banco, nunca em memória.
- **Idempotência:**
  - transferência, depósito, abertura de conta e empréstimo exigem o header `Idempotency-Key`;
  - no cadastro de cliente, a chave é derivada do CPF;
  - repetir o pedido devolve o resultado original.
- **Concorrência:** pedidos simultâneos com a mesma chave, boleto pago, parcela e aprovação PJ executam **uma vez**.
- **Tarifas e parcelas** entram numa conta interna do banco (tesouraria). Todo débito tem um crédito.
- **Logs sem dado sensível:** CPF mascarado, senha e token nunca aparecem.

## Estrutura

```
src/          API: resources (HTTP) → controllers (regras) → repositories (banco)
database/     schema do Core (database.sql)
risk_engine/  Motor de Risco + worker LLM
mock_bankslip/ provedor de boletos simulado
tests/        testes de integração (via HTTP) e unitários
docs/         RFC e documentação técnica
```

**Time:** Gabriel Farias De Marco · Lucas Rodrigues Hirashima · João Gabriel Iuzviak Mantagute
