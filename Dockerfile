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
COPY data/locations ./data/locations
COPY All_Districtof_India_*.xlsx ./
COPY All_Sub_Districtof_India_*.xlsx ./
COPY All_Villagesof_India_*.xlsx ./

# The baseline is synthetic and reproducible; ignored local artifacts are never
# required for a clean GitHub checkout to build. Keep it outside the mounted
# artifacts directory so the API can copy it into an empty first-run volume.
RUN python -m soil_npk.generator --output /tmp/npk-synthetic --samples 800 \
    && python -m soil_npk.training --labels /tmp/npk-synthetic/labels.csv --model /app/bootstrap_artifacts/npk_baseline.npz \
    && rm -r /tmp/npk-synthetic

EXPOSE 8000 8501
