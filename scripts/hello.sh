#!/bin/bash

for f in /opt/box/libs/* ; do source $f; done

usage() {
    echo "----------------- hello -----------------" 
    echo "A hello world function" 
    echo "hello [-h] [-l language] command"
    echo "    -h (opt)    : this helper"
    echo "    -l (opt)    : language"
    echo "        -l english (default)"
    echo "        -l french"
}

while getopts "hl:" option; do
case ${option} in
    h) usage && exit 0 ;;
    l) LANGUAGE=${OPTARG} ;;
    *) usage && exit 1 ;;
    esac
done
shift $(($OPTIND-1))

debug LANGUAGE=$LANGUAGE

case ${LANGUAGE} in
    english) success "hello world!" ;;
    french)  success "salut la compagnie !" ;;
    '')      success "hello world" ;;
    *)       error ${LANGUAGE} is unsupported language && exit 1 ;;
esac
