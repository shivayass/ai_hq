# Use the official Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements (if you have any)
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app files
COPY . .

# Expose the app port
EXPOSE 8080

ENV HF_TOKEN=$HF_TOKEN
ENV HUGGINGFACE_API_TOKEN=$HF_TOKEN

CMD ["python", "app.py"]
