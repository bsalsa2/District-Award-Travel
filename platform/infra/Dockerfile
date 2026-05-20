FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install -r requirements.txt

# Copy the application code
COPY . .

# Expose the ports
EXPOSE 8080
EXPOSE 8081

# Run the command to start the monitoring dashboard server
CMD ["python", "monitoring_dashboard.py"]
