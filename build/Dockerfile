FROM ubuntu:24.04

ENV TZ=Europe/Paris
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update
RUN apt upgrade -y -qq

# Installed packages 
RUN apt install -y -qq \
    sudo \
    curl wget \
    unzip \
    lsb-release \
    jq bc

WORKDIR /home/ubuntu
