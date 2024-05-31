#!/bin/sh

if [ -z "${@}" ] # empty box command

then # opens terminal
    docker compose \
        --env-file .env \
        run -it --rm -e "TERM=xterm-256color" \
        ubuntu /bin/bash

else # runs a script
    docker compose \
        --env-file .env \
        run -it --rm \
        ubuntu /opt/box/bin/box ${@}

fi