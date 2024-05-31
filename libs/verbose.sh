#!/bin/bash

# https://unix.stackexchange.com/questions/19323/what-is-the-caller-command
# https://askubuntu.com/questions/678915/whats-the-difference-between-and-in-bash
# https://stackoverflow.com/questions/918886/how-do-i-split-a-string-on-a-delimiter-in-bash
stacktrace() {

    local frame=1 trace="" LINE SUB FILE
    
    while read LINE SUB FILE < <(caller "$frame"); do
        FILEa=(${FILE//// })
        trace="${trace}${FILEa[-1]}:${SUB}:${LINE}>"
        ((frame++))
    done

    trace="${trace::-1} |"
    trace="${trace//main/}" 
    echo ${trace}

}

NC='\033[0m' # No Color
LRED='\033[0;91m'   ; critical () { echo -e "${LRED}$(stacktrace) $@${NC}"   ; }
RED='\033[0;31m'    ; error ()    { echo -e "${RED}$(stacktrace) $@${NC}"    ; }
ORANGE='\033[0;33m' ; warning ()  { echo -e "${ORANGE}$(stacktrace) $@${NC}" ; }
PURPLE='\033[0;35m' ; notice ()   { echo -e "${PURPLE}$(stacktrace) $@${NC}" ; }
CYAN='\033[0;36m'   ; info ()     { echo -e "${CYAN}$(stacktrace) $@${NC}"   ; }
GREEN='\033[0;32m'  ; success ()  { echo -e "${GREEN}$(stacktrace) $@${NC}"  ; }

GREY='\033[0;90m'   
debug () { if [ -n "${DEBUG}" ] ; then echo -e "${GREY}$(stacktrace) $@${NC}" ; fi ; }

assert () { 
    if [ "$1" -eq "0" ]
    then echo -e "${GREEN}${@:2} ok${NC}" 
    else echo -e "${RED}${@:2} failed${NC}" 
    fi
}