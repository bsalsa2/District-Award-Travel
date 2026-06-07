FROM python:3.9-slim

# Set working directory to /app
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Expose port 5000 for the API
EXPOSE 5000

# Run the command to start the API
CMD ["flask", "run", "--host=0.0.0.0"]
