FROM ubuntu:22.04

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

# Create ubuntu user
ENV USERNAME=ubuntu
ENV USER_UID=1001
ENV USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME
RUN chown --recursive $USERNAME:$USERNAME /home/$USERNAME

WORKDIR /home/$USERNAME