#!/bin/bash

if [ -n "${DEBUG}" ] ; then notice "debug mode on" ; fi 


# LOGGING ############################################################

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

} ; export -f stacktrace

critical () { LRED='\033[0;91m'   ; echo -e "${LRED}$(stacktrace) $@\033[0m"   ; } ; export -f critical
error ()    { RED='\033[0;31m'    ; echo -e "${RED}$(stacktrace) $@\033[0m"    ; } ; export -f error
warning ()  { ORANGE='\033[0;33m' ; echo -e "${ORANGE}$(stacktrace) $@\033[0m" ; } ; export -f warning
notice ()   { PURPLE='\033[0;35m' ; echo -e "${PURPLE}$(stacktrace) $@\033[0m" ; } ; export -f notice
info ()     { CYAN='\033[0;36m'   ; echo -e "${CYAN}$(stacktrace) $@\033[0m"   ; } ; export -f info
success ()  { GREEN='\033[0;32m'  ; echo -e "${GREEN}$(stacktrace) $@\033[0m"  ; } ; export -f success

debug () { if [ -n "${DEBUG}" ] ; then
              GREY='\033[0;90m'   ; echo -e "${GREY}$(stacktrace) $@\033[0m"   ; 
           fi ; 
         } ; export -f debug

# TESTING ############################################################

assert () { 
    if [ "$1" -eq "0" ]
    then echo -e "${GREEN}${@:2} ok${NC}" 
    else echo -e "${RED}${@:2} failed${NC}" 
    fi
} ; export -f assert

###############################################################


start_time=$(date +%s.%3N)

CMD=${1} && shift 1
debug command=$CMD
/home/ubuntu/scripts/${CMD}.sh $@

end_time=$(date +%s.%3N)
debug "$(echo $end_time - $start_time | bc)s"