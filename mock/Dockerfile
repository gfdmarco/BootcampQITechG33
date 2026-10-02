FROM python:3.11-slim

RUN pip install --no-cache-dir fastapi "uvicorn[standard]"

WORKDIR /mock
COPY bankslip_mock.py /mock/bankslip_mock.py

CMD ["uvicorn", "bankslip_mock:app", "--host", "0.0.0.0", "--port", "8080"]