#!/bin/bash

for f in /home/ubuntu/scripts/libs/* ; do source $f; done

if [ -n "${DEBUG}" ] ; then notice "debug mode on" ; fi 

start_time=$(date +%s.%3N)

CMD=${1} && shift 1
debug command=$CMD
/home/ubuntu/scripts/${CMD}.sh $@

end_time=$(date +%s.%3N)
debug "$(echo $end_time - $start_time | bc)s"