FROM python:3.13-slim

# Install system dependencies and build tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev gcc gfortran libatlas-base-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy only requirements first to leverage Docker cache
COPY requirements.txt /workspace/requirements.txt
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r /workspace/requirements.txt

# Default user/setup
ENV PYTHONUNBUFFERED=1

CMD ["/bin/bash"]
