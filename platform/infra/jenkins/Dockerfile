FROM jenkins/jenkins:lts-jdk17

# Install GPU dependencies
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nvidia-cuda-toolkit \
    nvidia-driver-535 \
    python3-pip \
    python3-dev \
    git \
    curl \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install NeMo framework
RUN pip3 install nvidia-nemo-toolkit[all]==1.15.0

# Install Morpheus
RUN pip3 install morpheus-ai

# Install Jenkins plugins
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN /usr/local/bin/install-plugins.sh < /usr/share/jenkins/ref/plugins.txt

# Configure Jenkins
COPY init.groovy.d /usr/share/jenkins/ref/init.groovy.d/

# Set up GPU environment
ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES compute,utility

# Create GPU workspace
RUN mkdir -p /workspace/gpu && \
    chown -R jenkins:jenkins /workspace

USER jenkins
