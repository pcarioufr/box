#!/bin/sh

ROOT="./"
export DATA="${ROOT}data"
export SCRIPTS="${ROOT}scripts"
export ENV="${ROOT}.env"
export BUILD="${ROOT}build"


usage() {
    echo "----------------- box -----------------" 
    echo "A wrapper on docker for The Box" 
    echo "hello [-h] [-b] command (opt)"
    echo "    -h (opt)      : this helper"
    echo "    -b (opt)      : (re)build The Box docker image"
    echo "    command (opt) : command to pass to the box entry script"
    echo "                    passing no command opens a bash script"
}

while getopts "hb" option; do
case ${option} in
    h) usage && exit 0 ;;
    b) _b=1 ;;
    *) usage && exit 1 ;;
    esac
done
shift $(($OPTIND-1))

if [ -n "_b" ] # empty box command
then # opens terminal
    docker compose build ubuntu
    exit 0
fi


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