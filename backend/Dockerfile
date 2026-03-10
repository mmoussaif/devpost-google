FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create frontend directory — frontend files are copied separately during deploy
# The deploy.sh script builds from root context; frontend is served via main.py's relative path
RUN mkdir -p /app/frontend

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]
