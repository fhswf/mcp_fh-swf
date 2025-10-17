FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Copy data directory (nur vpis-Unterordner)
COPY data/vpis/ ./data/vpis/

# Command to run the application
CMD ["python", "src/main.py"]


