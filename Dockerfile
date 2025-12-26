# Use a base image with CUDA and cuDNN support
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04

# Defines non-interactive mode for apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Installs Python, FFmpeg and system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    git \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# Sets the working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Default command
CMD ["python3", "worker_service.py"]