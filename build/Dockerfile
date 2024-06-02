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
ENV USER_UID=1001
ENV GROUPNAME=box
ENV USER_GID=1001
RUN groupadd --gid $USER_GID $GROUPNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME
RUN chown --recursive $USERNAME:$USERNAME /home/$USERNAME

WORKDIR /home/box
