# TEMPLATE - NOT TESTED. Role D owns this file. Purpose: run the simulator headless as a Nebius Serverless Job.
# Build:  docker build -t second-look-sim -f docker/Dockerfile .
# Test:   docker run --rm second-look-sim python sim/gantry_demo.py
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libosmesa6 libglu1-mesa && rm -rf /var/lib/apt/lists/*
ENV MUJOCO_GL=osmesa PYOPENGL_PLATFORM=osmesa PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Never put API keys in the image. Pass them at run time (see docker/nebius_job_example.sh).
CMD ["python", "sim/gantry_demo.py"]
