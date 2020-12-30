#!/bin/bash

sendMinecraftCommand() {
    /usr/bin/screen -r mc-${mcServer} -p0 -X stuff "${mcCmd} ${mcArgs}\n"
    sleep 1
    /usr/bin/screen -S mc-${mcServer} -X hardcopy /home/minecraft/${mcServer}/mcOut.log
}

if [[ ${#} -gt 2 ]]; then
    mcCmd=${1}
    mcServer=${2}
    mcArgs=${@:3}
    sendMinecraftCommand
    echo "Command probably worked"
else
    echo -e "Error: missing arguments.\n\nUsage: /command ServerName arguments go here"
fi
