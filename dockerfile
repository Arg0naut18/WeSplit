FROM python:3.11

USER root

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt && \
    chmod 777 -R /app

USER 1001

CMD ["python", "main.py"]
