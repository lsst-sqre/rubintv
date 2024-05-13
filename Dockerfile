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

USER root

# Install required packages
RUN apt-get update && \
    apt-get install -y \
    libsasl2-dev \
    python-dev \
    libldap2-dev \
    git \
    inetutils-ping \
    vim \
    nano \
    curl \
    procps \
    findutils \
    libssl-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/rubintv/
COPY . .

# Install dependencies
RUN pip install -r requirements.txt && \
    python setup.py install

# Adjust permissions for executable
RUN chmod +x /usr/src/rubintv/start-daemon.sh

# Expose the port.
EXPOSE 8000

CMD ["/usr/src/rubintv/start-daemon.sh"]
