# Use Python base image
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Make sure Render's environment vars are available
ENV HF_TOKEN=${HF_TOKEN}
ENV HF_MODEL=${HF_MODEL}
ENV HUGGINGFACE_API_TOKEN=${HF_TOKEN}

# Run your app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
