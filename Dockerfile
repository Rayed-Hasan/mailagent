FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Run with environment variable controlling mode
CMD ["uvicorn", "mailagent.dashboard.app:app", "--host", "0.0.0.0", "--port", "8000"]
