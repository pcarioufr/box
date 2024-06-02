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


# Create box user
ENV USERNAME=box

RUN useradd -g users -G sudo -m $USERNAME -d /home/$USERNAME
RUN echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME
RUN chmod 0440 /etc/sudoers.d/$USERNAME
RUN usermod --shell /bin/bash $USERNAME

USER $USERNAME
# RUN chown --recursive $USERNAME:$USERNAME /home/$USERNAME

WORKDIR /home/$USERNAME
