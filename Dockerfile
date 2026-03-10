FROM python:3.12-slim-bookworm

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev 

COPY backend/app/ app/

COPY data/model.joblib model/model.joblib

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]