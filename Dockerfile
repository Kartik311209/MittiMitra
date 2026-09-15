FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY dashboard.py README.md ./
COPY assets ./assets
COPY artifacts ./artifacts
COPY data/synthetic ./data/synthetic
COPY data/locations ./data/locations
COPY All_Districtof_India_*.xlsx ./
COPY All_Sub_Districtof_India_*.xlsx ./
COPY All_Villagesof_India_*.xlsx ./

EXPOSE 8000 8501
