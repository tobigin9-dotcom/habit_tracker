FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir poetry==1.8.4
COPY pyproject.toml ./
RUN poetry config virtualenvs.create false && poetry install --only main --no-root --no-interaction --no-ansi
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
