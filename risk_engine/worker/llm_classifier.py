"""
LLM Classifier Worker
=====================
Roda assincronamente (a cada 6h via APScheduler) para classificar
o perfil de risco de cada cliente com base no histórico de transações.

Fluxo:
  1. Busca customer_keys que precisam de reavaliação (há > 24h ou UNKNOWN).
  2. Para cada cliente, consulta o extrato de 30 dias no Core API.
  3. Resume o histórico e envia para Groq (Llama 3) classificar o risco (c/ retries).
  4. Atualiza o risk_profile via PATCH /risk_profile/{key} no Risk Engine.
"""

import os
import time
import logging
import requests
import re
from datetime import datetime, timezone, timedelta
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

# ── Prompt Otimizado ────────────────────────────────────────────────────────
CLASSIFICATION_PROMPT = """
Você é um analista antifraude experiente.
Analise o extrato abaixo e classifique o risco do cliente.
Critérios de Risco:
- LOW: Transações de baixo valor, padrões consistentes, focado em PIX/TED local.
- MEDIUM: Transações de valor moderado, picos ocasionais.
- HIGH: Valores excessivamente altos atípicos, uso frequente do canal "international", ou muitas transações suspeitas.

Responda APENAS com a palavra: low, medium ou high.

Histórico (últimas {n} transações):
{history}
""".strip()


class LLMClassifier:
    def __init__(self):
        self.groq_client = Groq(api_key=GROQ_API_KEY)
        self.headers = {"INTERNAL-TOKEN": INTERNAL_TOKEN}

    # ── Busca clientes a classificar (Custo & Escala) ───────────────────────
    def _fetch_customers_to_evaluate(self) -> list[str]:
        """
        Retorna clientes cujo score é 'unknown' ou cuja última avaliação
        foi há mais de 24 horas para economizar custos de LLM.
        """
        try:
            resp = requests.get(
                f"{RISK_ENGINE_URL}/risk_profile",
                headers=self.headers,
                timeout=5
            )
            if resp.status_code == 200:
                profiles = resp.json().get("profiles", [])
                to_evaluate = []
                now = datetime.now(timezone.utc)
                
                for p in profiles:
                    if p["score"] == "unknown":
                        to_evaluate.append(p["customer_key"])
                        continue
                        
                    try:
                        # Parsing the ISO format
                        dt_str = p.get("last_evaluated_at", "")
                        last_eval = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                        if last_eval.tzinfo is None:
                            last_eval = last_eval.replace(tzinfo=timezone.utc)
                            
                        if (now - last_eval) > timedelta(hours=24):
                            to_evaluate.append(p["customer_key"])
                    except Exception:
                        to_evaluate.append(p["customer_key"])

                return to_evaluate
        except requests.RequestException as e:
            logger.error(f"Falha ao buscar perfis do Risk Engine: {e}")
        return []

    # ── Busca histórico de transações no Core ───────────────────────────────
    def _fetch_transaction_history(self, customer_key: str) -> list[dict]:
        try:
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
            amount_brl = tx.get("amount", 0) / 100
            fee_brl    = tx.get("fee_amount", 0) / 100
            lines.append(
                f"- {tx.get('type','?')} via {tx.get('channel','?')} | "
                f"R$ {amount_brl:.2f} (tarifa R$ {fee_brl:.2f}) | "
                f"{tx.get('created_at', '?')}"
            )
        return "\n".join(lines)

    # ── Classifica via Groq (Fault Tolerance & Otimização) ──────────────────
    def _classify_with_llm(self, history_summary: str, n: int) -> str:
        prompt = CLASSIFICATION_PROMPT.format(history=history_summary, n=n)
        
        max_retries = 3
        backoff_factor = 2
        
        for attempt in range(max_retries):
            try:
                response = self.groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "Você é um classificador de risco. Responda APENAS com uma palavra estritamente: low, medium, ou high."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=5,
                    temperature=0.0
                )
                score = response.choices[0].message.content.strip().lower()
                
                # Remove qualquer pontuação vazada da IA
                score = re.sub(r'[^a-z]', '', score)
                
                if score not in {"low", "medium", "high"}:
                    logger.warning(f"Groq retornou valor inesperado: '{score}'. Usando 'unknown'.")
                    return "unknown"
                    
                return score
                
            except Exception as e:
                wait = backoff_factor ** attempt
                logger.warning(f"Groq indisponível (tentativa {attempt + 1}/{max_retries}). Aguardando {wait}s: {e}")
                time.sleep(wait)
                
        logger.error("Groq permanentemente indisponível após retentativas.")
        return None

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
        logger.info(f"{len(customer_keys)} clientes precisam de reavaliação.")

        for customer_key in customer_keys:
            transactions  = self._fetch_transaction_history(customer_key)
            summary       = self._build_history_summary(transactions)
            score         = self._classify_with_llm(summary, len(transactions))

            if score is None:
                logger.error(f"Abortando atualização para {customer_key} devido a falha permanente no Groq.")
                continue

            reason = f"LLM ({GROQ_MODEL}) classificou com base em {len(transactions)} transações via heurística de reavaliação."
            self._update_risk_profile(customer_key, score, reason)
            logger.info(f"Cliente {customer_key} → score atualizado para: {score}")

        logger.info("LLM Classifier Worker finalizado.")
