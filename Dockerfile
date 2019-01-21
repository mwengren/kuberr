FROM ubuntu:18.04

# Define some target paths for environment variables to allow running outside of a Kubernetes cluster, if necessary:
ENV GOOGLE_APPLICATION_CREDENTIALS=/tmp/kuberr/service-account.json
ENV KUBECONFIG=/tmp/kuberr/config

ENV ERDDAP_VERSION 1.82

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      git \
      python3 \
      python3-dev \
      python3-pip \
      python3-setuptools \
      libcurl4-openssl-dev \
      libssl-dev \
      build-essential \
      && \
    apt-get purge && apt-get clean

ARG VERSION=0.1.0

WORKDIR /tmp/kuberr

COPY requirements.txt requirements.txt
COPY kuberr kuberr
COPY setup.py setup.py
COPY README.md README.md
RUN python3 -m pip install --upgrade pip setuptools wheel
#RUN pip3 install --no-cache-dir \
#        kuberr==${VERSION} \
#        -r requirements.txt

#RUN pip3 install . \
#        -r requirements.txt

RUN python3 setup.py install

CMD ["erddap_config"]
