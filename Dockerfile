FROM python:3.12-slim
WORKDIR /app
COPY server.py app.html ./
ENV PYTHONUNBUFFERED=1 BRIDGE_HTTPS=1 BRIDGE_DB=/data/monitoring.sqlite3
EXPOSE 8765
CMD ["python", "server.py", "--lan", "--no-browser"]
