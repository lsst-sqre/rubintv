FROM continuumio/miniconda3:latest

WORKDIR /usr/src/rubintv/
COPY . .

# Create a non-root user and adjust permissions
RUN useradd -m rubintv
RUN chown -R rubintv:rubintv /usr/src/rubintv
USER rubintv

# Set a conda environment
RUN conda create -y -n rubintv python=3.11

# Make RUN commands use the new environment:
SHELL ["conda", "run", "-n", "rubintv", "/bin/bash", "-c"]

# Install conda dependencies
RUN conda config --add channels conda-forge && \
    conda install -y mamba && \ 
    mamba install -y conda-build anaconda-client setuptools_scm

RUN conda build -c conda-forge --prefix-length 100 . && \
    conda install -y -c conda-forge --use-local rubintv

# Install safir
RUN pip install safir

# Adjust permissions for executable
RUN chmod +x /usr/src/rubintv/start-daemon.sh

# Expose the port.
EXPOSE 8000

CMD ["/usr/src/rubintv/start-daemon.sh"]
