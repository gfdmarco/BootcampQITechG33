"""
Scheduler do LLM Worker
========================
Configura o APScheduler para rodar o LLM Classifier a cada 6 horas.

Para iniciar manualmente (dev):
    python worker/scheduler.py

Em produção, o docker-compose pode subir este processo como um segundo
comando no container risk_engine, ou como um container separado
compartilhando o mesmo volume.
"""

import logging
import os
from apscheduler.schedulers.blocking import BlockingScheduler
from worker.llm_classifier import LLMClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Intervalo configurável via env — padrão 6 horas
WORKER_INTERVAL_HOURS = int(os.getenv("WORKER_INTERVAL_HOURS", "6"))


def run_classification_job():
    classifier = LLMClassifier()
    classifier.run()


if __name__ == "__main__":
    logger.info(f"Scheduler iniciado. Classificação a cada {WORKER_INTERVAL_HOURS}h.")

    # Roda uma vez imediatamente ao subir (warm-up)
    run_classification_job()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_classification_job,
        trigger="interval",
        hours=WORKER_INTERVAL_HOURS,
        id="llm_risk_classifier"
    )
    scheduler.start()
