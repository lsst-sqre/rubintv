# This Dockerfile is used to build the Rubintv on a commit basis.
# The GH action will build the image and push it to the registry.
# The image will be used to deploy the application on dev servers.
# Note:
# I was not able to use the conda recipe to build the image,
# faced several issues which at the end I was not able to resolve
# and decided to use the python image instead.
# This is a temporary solution, and I will work on a better approach
# to build the image using conda.
# TODO: DM-43222.

FROM python:3.12.3-slim-bullseye

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    libsasl2-dev \
    python-dev \
    libldap2-dev \
    inetutils-ping \
    vim \
    nano \
    procps \
    findutils \
    libssl-dev \
    git curl unzip xz-utils zip libglu1-mesa \
    python3-venv \
    libgl1-mesa-glx && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Add a user with UID and GID 1000
RUN groupadd -g 1000 rubintv && \
useradd -r -u 1000 -g rubintv -m rubintv

# Setup work directory and adjust permissions
WORKDIR /usr/src/rubintv
RUN chown -R rubintv:rubintv /usr/src/rubintv

# Switch to the new user
USER rubintv

# Setup Flutter
RUN git clone https://github.com/flutter/flutter.git /home/rubintv/flutter
ENV PATH="/home/rubintv/flutter/bin:/home/rubintv/flutter/bin/cache/dart-sdk/bin:${PATH}"
RUN flutter doctor && \
    flutter channel master && \
    flutter upgrade

# Create a virtual environment
RUN python -m venv venv

# Activate virtual environment
ENV PATH="/usr/src/rubintv/venv/bin:$PATH"

# Copy the rest of the application
COPY --chown=rubintv:rubintv . .

# Install Python dependencies
RUN pip install -r requirements.txt && \
    python setup.py install

# Adjust permissions for executable
RUN chmod +x start-daemon.sh

# Expose the port and define the CMD
EXPOSE 8000
CMD ["./start-daemon.sh"]
