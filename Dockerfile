FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY src ./src
COPY streamlit_app.py .
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8501
CMD ["./start.sh"]

