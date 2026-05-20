# Use NVIDIA RAPIDS base image for GPU acceleration
FROM nvcr.io/nvidia/rapidsai/rapidsai-core:23.10-cuda12.2-py3.10

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3-dev \
    libpq-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV CUDA_HOME=/usr/local/cuda

# Run the processor service
CMD ["python3", "processor_service.py"]
