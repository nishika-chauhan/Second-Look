# TEMPLATE - NOT TESTED. Role D owns this file. Purpose: run the simulator headless as a Nebius Serverless Job.
# Build:  docker build -t second-look-sim -f docker/Dockerfile .
# Test:   docker run --rm second-look-sim python sim/gantry_demo.py

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libosmesa6 \
    libglu1-mesa \
    libxcb1 \
    libx11-6 \
    libxext6 \
    libsm6 \
    libxrender1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV MUJOCO_GL=osmesa \
    PYOPENGL_PLATFORM=osmesa \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

# Install CPU-only PyTorch and its dependencies
# Cache pip downloads across failed Docker builds
RUN --mount=type=cache,target=/root/.cache/pip \
    pip --timeout 300 --retries 10 install \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.11.0 torchvision==0.26.0

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir "lerobot[smolvla]==0.6.1"

COPY . .

# Pass API keys at runtime, never bake them into the image.
CMD ["python", "sim/gantry_demo.py"]
