"""
LLM Classifier Worker
=====================
Roda assincronamente (a cada 6h via APScheduler) para classificar
o perfil de risco de cada cliente com base no histórico de transações.

Fluxo:
  1. Busca todos os customer_keys conhecidos no db_risk (risk_profile).
  2. Para cada cliente, consulta o extrato de 30 dias no Core API.
  3. Resume o histórico e envia para Groq (Llama 3) classificar o risco.
  4. Atualiza o risk_profile via PATCH /risk_profile/{key} no Risk Engine.
     → O endpoint de PATCH já sincroniza o Redis automaticamente.

Clientes sem transações: score mantido como UNKNOWN.
Groq indisponível: worker loga o erro e pula o cliente (tenta no próximo ciclo).
"""

import os
import logging
import requests
from groq import Groq

logger = logging.getLogger(__name__)

# ── Configuração via env ────────────────────────────────────────────────────
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL         = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

CORE_API_URL       = os.getenv("CORE_API_URL", "http://api:3000")
RISK_ENGINE_URL    = os.getenv("RISK_ENGINE_URL", "http://risk_engine:3000")
INTERNAL_TOKEN     = os.getenv("INTERNAL_TOKEN", "risk_default_token")

STATEMENT_DAYS     = 30
STATEMENT_LIMIT    = 50  # máx de transações analisadas por cliente

# ── Prompt ──────────────────────────────────────────────────────────────────
CLASSIFICATION_PROMPT = """
Você é um analista de risco de um banco digital. Analise o histórico de
transações financeiras abaixo e classifique o perfil de risco do cliente
como exatamente uma dessas três palavras: low, medium ou high.

Critérios:
- low: transações regulares, valores consistentes, sem picos atípicos.
- medium: alguns picos de valor, padrão misto ou histórico curto.
- high: transferências de alto valor atípicas, muitas transações em pouco
  tempo, padrão inconsistente ou suspeito.

Responda APENAS com uma das três palavras, sem pontuação ou explicação.

Histórico (últimas {n} transações):
{history}
""".strip()


class LLMClassifier:
    def __init__(self):
        self.groq_client = Groq(api_key=GROQ_API_KEY)
        self.headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}

    # ── Busca clientes a classificar ────────────────────────────────────────
    def _fetch_customers_to_evaluate(self) -> list[str]:
        """
        Retorna todos os customer_keys do db_risk ordenados pelo mais antigo.
        Clientes novos (sem profile) serão inseridos na primeira chamada ao /evaluate.
        """
        try:
            resp = requests.get(
                f"{RISK_ENGINE_URL}/risk_profile",
                headers=self.headers,
                timeout=5
            )
            if resp.status_code == 200:
                return [p["customer_key"] for p in resp.json().get("profiles", [])]
        except requests.RequestException as e:
            logger.error(f"Falha ao buscar perfis do Risk Engine: {e}")
        return []

    # ── Busca histórico de transações no Core ───────────────────────────────
    def _fetch_transaction_history(self, customer_key: str) -> list[dict]:
        """
        Chama o Core API internamente para obter o extrato de 30 dias.
        Usa INTERNAL-TOKEN — não precisa de JWT do cliente.
        """
        try:
            # Busca contas do cliente via rota interna
            accounts_resp = requests.get(
                f"{CORE_API_URL}/accounts",
                headers={**self.headers, "customer_key": customer_key},
                params={"limit": 10, "page": 1},
                timeout=5
            )
            if accounts_resp.status_code != 200:
                return []

            accounts = accounts_resp.json().get("accounts", [])
            transactions = []

            for account in accounts:
                stmt_resp = requests.get(
                    f"{CORE_API_URL}/accounts/{account['account_key']}/statement",
                    headers=self.headers,
                    params={"limit": STATEMENT_LIMIT, "page": 1},
                    timeout=5
                )
                if stmt_resp.status_code == 200:
                    transactions.extend(
                        stmt_resp.json().get("transactions_list", [])
                    )

            return transactions[:STATEMENT_LIMIT]

        except requests.RequestException as e:
            logger.warning(f"Falha ao buscar histórico do cliente {customer_key}: {e}")
            return []

    # ── Sumariza o histórico para o prompt ──────────────────────────────────
    def _build_history_summary(self, transactions: list[dict]) -> str:
        if not transactions:
            return "Nenhuma transação encontrada no período."

        lines = []
        for tx in transactions:
            amount_brl = tx.get("amount", 0) / 100  # centavos → reais
            fee_brl    = tx.get("fee_amount", 0) / 100
            lines.append(
                f"- {tx.get('type','?')} via {tx.get('channel','?')} | "
                f"R$ {amount_brl:.2f} (tarifa R$ {fee_brl:.2f}) | "
                f"{tx.get('created_at', '?')}"
            )
        return "\n".join(lines)

    # ── Classifica via Groq ─────────────────────────────────────────────────
    def _classify_with_llm(self, history_summary: str, n: int) -> str:
        prompt = CLASSIFICATION_PROMPT.format(history=history_summary, n=n)
        try:
            response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0.0  # determinístico para decisões financeiras
            )
            score = response.choices[0].message.content.strip().lower()
            if score not in {"low", "medium", "high"}:
                logger.warning(f"Groq retornou valor inesperado: '{score}'. Usando 'unknown'.")
                return "unknown"
            return score
        except Exception as e:
            logger.error(f"Groq indisponível: {e}")
            return None  # None = pular este cliente, tentar no próximo ciclo

    # ── Atualiza o Risk Engine ───────────────────────────────────────────────
    def _update_risk_profile(self, customer_key: str, score: str, reason: str) -> None:
        try:
            requests.patch(
                f"{RISK_ENGINE_URL}/risk_profile/{customer_key}",
                headers=self.headers,
                json={"score": score, "reason": reason},
                timeout=5
            )
        except requests.RequestException as e:
            logger.error(f"Falha ao atualizar perfil de {customer_key}: {e}")

    # ── Ponto de entrada do Worker ───────────────────────────────────────────
    def run(self) -> None:
        logger.info("LLM Classifier Worker iniciado.")

        if not GROQ_API_KEY:
            logger.error("GROQ_API_KEY não configurada. Worker abortando.")
            return

        customer_keys = self._fetch_customers_to_evaluate()
        logger.info(f"{len(customer_keys)} clientes para avaliar.")

        for customer_key in customer_keys:
            transactions  = self._fetch_transaction_history(customer_key)
            summary       = self._build_history_summary(transactions)
            score         = self._classify_with_llm(summary, len(transactions))

            if score is None:
                logger.warning(f"Pulando {customer_key} — Groq indisponível.")
                continue

            reason = f"LLM ({GROQ_MODEL}) classificou com base em {len(transactions)} transações."
            self._update_risk_profile(customer_key, score, reason)
            logger.info(f"Cliente {customer_key} → score: {score}")

        logger.info("LLM Classifier Worker finalizado.")
