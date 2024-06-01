#!/bin/sh

export DATA="./data"
export SCRIPTS="./scripts"

if [ -z "${@}" ] # empty box command

then # opens terminal
    docker compose \
        run -it --rm -e "TERM=xterm-256color" \
        ubuntu /bin/bash

else # runs a script
    docker compose \
        run -it --rm \
        ubuntu /opt/box/main.sh ${@}

fi