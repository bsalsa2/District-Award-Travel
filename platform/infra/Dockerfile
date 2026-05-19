FROM python:3.9-slim

# Set the working directory to /app
WORKDIR /app

# Copy the alerting system script
COPY alerting_system.py /app/alerting_system.py

# Install the required dependencies
RUN pip install psutil

# Run the alerting system script
CMD ["python", "alerting_system.py"]
