# Planetary EOS Lab Docker Image
#
# This Dockerfile creates a containerized environment for running Planetary EOS Lab.
# Note: Perple_X must be provided separately due to licensing.
#
# Build: docker build -t planetary-eos-lab .
# Run:   docker run -p 8501:8501 -v /path/to/perplex:/opt/perplex planetary-eos-lab

FROM python:3.11-slim

LABEL maintainer="Emma Vellard <emma.vellard@outlook.fr>"
LABEL description="Planetary EOS Lab - GUI workflow for planetary thermodynamics"
LABEL version="1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy application files
COPY . /app/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Create directories for Perple_X (to be mounted as volumes)
RUN mkdir -p /opt/perplex /app/outputs /app/compositions /app/configs

# Copy example config
RUN if [ ! -f /app/configs/models.json ]; then \
        cp /app/configs/models.example.json /app/configs/models.json; \
    fi

# Set default Perple_X directory (override with environment variable)
ENV PERPLEX_DIR=/opt/perplex
ENV PERPLEX_DATABASE=stx21
ENV PERPLEX_LOG_LEVEL=INFO

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=5).read()" || exit 1

# Default command: launch GUI
CMD ["planetary-eos-gui", "--address", "0.0.0.0"]
