#!/bin/sh
set -e

uvicorn cx_assist.api:app --host 127.0.0.1 --port 8000 &
exec streamlit run streamlit_app.py \
  --server.address 0.0.0.0 \
  --server.port 8501 \
  --server.headless true \
  --browser.gatherUsageStats false

