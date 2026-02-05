#!/bin/sh

# Verify services/compose.yml exists
COMPOSE_FILE="services/compose.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "ERROR: $COMPOSE_FILE not found in $(pwd)" >&2
    exit 1
fi

usage() {
    echo "----------------- box -----------------" 
    echo "A wrapper on docker for The Box" 
    echo "hello [-h] [-b] command (opt)"
    echo "    -h (opt)      : this helper"
    echo "    -b (opt)      : (re)build The Box docker image"
    echo "    command (opt) : command to pass to the box entry script"
    echo "                    passing no command opens a bash shell"
}

while getopts "hb" option; do
case ${option} in
    h) usage && exit 0 ;;
    b) _b=1 ;;
    *) usage && exit 1 ;;
    esac
done
shift $(($OPTIND-1))

# Detect if we have a TTY
if [ -t 0 ]; then
    TTY_FLAGS="-it"
else
    TTY_FLAGS="-T"
fi

if [ -n "${_b}" ] # -b option
then # build command
    docker compose -f "$COMPOSE_FILE" build ubuntu
    exit 0
fi

if [ -z "${*}" ] # empty command line

then # opens terminal
    docker compose -f "$COMPOSE_FILE" \
        run $TTY_FLAGS --rm \
        ubuntu /bin/bash

else # runs a script
    docker compose -f "$COMPOSE_FILE" \
        run $TTY_FLAGS --rm \
        ubuntu /opt/box/main ${@}

fi