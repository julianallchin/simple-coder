FROM python:3.9-slim

# Install common development tools
RUN apt-get update && apt-get install -y \
    git \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set up a working directory
WORKDIR /workspace

# Run a shell to keep the container running
CMD ["/bin/sh"]
