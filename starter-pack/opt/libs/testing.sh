#!/bin/bash

assert () { 
    if [ "$1" -eq "0" ]
    then echo -e "${GREEN}${@:2} ok${NC}" 
    else echo -e "${RED}${@:2} failed${NC}" 
    fi
} ; export -f assert
