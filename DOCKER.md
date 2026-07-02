## Docker Usage Guide

Run Planetary EOS Lab in a Docker container for consistent, isolated environments.

## Quick Start

### Prerequisites
- Docker installed
- Perple_X downloaded to your local machine

### Basic Usage

1. **Build the image**
   ```bash
   docker build -t planetary-eos-lab .
   ```

2. **Run with GUI**
   ```bash
   docker run -p 8501:8501 \
     -v /path/to/your/perplex:/opt/perplex:ro \
     -v $(pwd)/outputs:/app/outputs \
     -v $(pwd)/compositions:/app/compositions \
     planetary-eos-lab
   ```

3. **Open browser**
   Navigate to http://localhost:8501

### Using Docker Compose (Recommended)

1. **Edit `docker-compose.yml`**
   Update the Perple_X path:
   ```yaml
   volumes:
     - /path/to/your/perplex:/opt/perplex:ro
   ```

2. **Start services**
   ```bash
   docker-compose up -d
   ```

3. **View logs**
   ```bash
   docker-compose logs -f
   ```

4. **Stop services**
   ```bash
   docker-compose down
   ```

## Volume Mounts

Required volumes:
- **Perple_X**: Mount your local Perple_X installation
  ```
  -v /path/to/perplex:/opt/perplex:ro
  ```
  The `:ro` makes it read-only for safety.

Optional volumes:
- **Outputs**: Persist generated files
  ```
  -v $(pwd)/outputs:/app/outputs
  ```

- **Compositions**: Persist composition files
  ```
  -v $(pwd)/compositions:/app/compositions
  ```

- **Config**: Use custom configuration
  ```
  -v $(pwd)/configs/models.json:/app/configs/models.json
  ```

## Environment Variables

Configure via `-e` flag or in `docker-compose.yml`:

```bash
docker run -p 8501:8501 \
  -e PERPLEX_DIR=/opt/perplex \
  -e PERPLEX_DATABASE=stx21 \
  -e PERPLEX_LOG_LEVEL=DEBUG \
  planetary-eos-lab
```

Available variables:
- `PERPLEX_DIR`: Path to Perple_X (default: `/opt/perplex`)
- `PERPLEX_DATABASE`: Database to use (default: `stx21`)
- `PERPLEX_LOG_LEVEL`: Logging level (default: `INFO`)

## CLI Commands in Docker

### Interactive Shell
```bash
docker run -it --rm \
  -v /path/to/perplex:/opt/perplex:ro \
  -v $(pwd)/outputs:/app/outputs \
  planetary-eos-lab /bin/bash
```

Then run commands:
```bash
planetary-eos-run --help
planetary-eos-compositions
planetary-eos-plot
```

### One-off Commands
```bash
# Generate compositions
docker run --rm \
  -v /path/to/perplex:/opt/perplex:ro \
  -v $(pwd)/outputs:/app/outputs \
  planetary-eos-lab \
  planetary-eos-compositions

# Run pipeline
docker run --rm \
  -v /path/to/perplex:/opt/perplex:ro \
  -v $(pwd)/outputs:/app/outputs \
  planetary-eos-lab \
  planetary-eos-run --project moon_far_highlands_surface_proxy
```

### Using docker-compose exec
```bash
# Start services
docker-compose up -d

# Run CLI commands
docker-compose exec planetary-eos-cli planetary-eos-run --help
docker-compose exec planetary-eos-cli planetary-eos-compositions
```

## Multi-stage Builds (Advanced)

For smaller production images, use multi-stage build:

```dockerfile
# Build stage
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Runtime stage
FROM python:3.11-slim
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*
COPY . /app
WORKDIR /app
CMD ["planetary-eos-gui"]
```

## Platform-Specific Notes

### macOS (Apple Silicon)
```bash
# Build for x86_64 architecture
docker build --platform linux/amd64 -t planetary-eos-lab .
```

### Windows
Use forward slashes in volume paths:
```bash
docker run -p 8501:8501 \
  -v C:/Users/YourName/perplex:/opt/perplex:ro \
  planetary-eos-lab
```

Or use WSL2 paths:
```bash
docker run -p 8501:8501 \
  -v /mnt/c/Users/YourName/perplex:/opt/perplex:ro \
  planetary-eos-lab
```

## Troubleshooting

### Container won't start
Check logs:
```bash
docker logs planetary-eos-lab
```

### Perple_X not found
Verify mount:
```bash
docker run --rm \
  -v /path/to/perplex:/opt/perplex \
  planetary-eos-lab \
  ls -la /opt/perplex
```

Should show:
```
bin/
datafiles/
```

### Permission issues
On Linux, ensure user has permissions:
```bash
docker run --user $(id -u):$(id -g) \
  -v /path/to/perplex:/opt/perplex:ro \
  planetary-eos-lab
```

### Port already in use
Use different port:
```bash
docker run -p 8502:8501 planetary-eos-lab
```
Then access at http://localhost:8502

### GUI doesn't load
1. Check container is running:
   ```bash
   docker ps
   ```

2. Check health:
   ```bash
   docker inspect --format='{{json .State.Health}}' planetary-eos-lab
   ```

3. Test locally:
   ```bash
   curl http://localhost:8501/_stcore/health
   ```

## Production Deployment

### Behind Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name perplex.example.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### With HTTPS (Let's Encrypt)

```yaml
# docker-compose.yml with Caddy reverse proxy
services:
  planetary-eos-lab:
    # ... same as before ...

  caddy:
    image: caddy:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - planetary-eos-lab

volumes:
  caddy_data:
  caddy_config:
```

```
# Caddyfile
perplex.example.com {
    reverse_proxy planetary-eos-lab:8501
}
```

## Resource Limits

Limit CPU and memory usage:

```yaml
services:
  planetary-eos-lab:
    # ... other config ...
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Persistent Data

Create named volumes for persistence:

```yaml
volumes:
  perplex_outputs:
  perplex_compositions:

services:
  planetary-eos-lab:
    volumes:
      - perplex_outputs:/app/outputs
      - perplex_compositions:/app/compositions
```

## Building Custom Images

Extend the base image:

```dockerfile
FROM planetary-eos-lab:1.0

# Add custom configurations
COPY custom_configs/ /app/configs/

# Install additional tools
RUN apt-get update && apt-get install -y custom-tool

# Add custom scripts
COPY scripts/ /app/scripts/
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Build Docker Image

on:
  push:
    tags:
      - 'v*'

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build image
        run: docker build -t planetary-eos-lab:${{ github.ref_name }} .

      - name: Push to registry
        run: |
          echo "${{ secrets.DOCKER_PASSWORD }}" | docker login -u "${{ secrets.DOCKER_USERNAME }}" --password-stdin
          docker push planetary-eos-lab:${{ github.ref_name }}
```

## Security Best Practices

1. **Use specific versions**
   ```dockerfile
   FROM python:3.11.6-slim
   ```

2. **Don't run as root**
   ```dockerfile
   RUN useradd -m -u 1000 appuser
   USER appuser
   ```

3. **Scan for vulnerabilities**
   ```bash
   docker scan planetary-eos-lab
   ```

4. **Use secrets properly**
   ```bash
   docker run --secret id=myconfig,src=./config.json planetary-eos-lab
   ```

## Getting Help

- Docker issues: Check logs with `docker logs`
- Planetary EOS Lab issues: [GitHub Issues](https://github.com/EmmaVellard/planetary-eos-lab/issues)
- Docker documentation: https://docs.docker.com/
