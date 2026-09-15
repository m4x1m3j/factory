FROM docker/sandbox-templates:copilot-docker

USER root

# Install system dependencies including just and openssh-client
RUN apt-get update && \
    apt-get install -y --no-install-recommends just openssh-client && \
    rm -rf /var/lib/apt/lists/*

# Pre-populate known hosts for github.com system-wide
RUN ssh-keyscan -t ed25519,rsa github.com >> /etc/ssh/ssh_known_hosts && \
    chmod 644 /etc/ssh/ssh_known_hosts

# Copy rtk CLI into system path
COPY --chmod=755 rtk /usr/local/bin/rtk

USER agent
