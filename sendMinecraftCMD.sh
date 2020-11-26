#!/bin/bash

sendMinecraftCommand() {
    /usr/bin/screen -r mc-${mcWorld} -p0 -X stuff "${mcCmd} ${mcArgs}\n"
}

if [[ ${#} -gt 2 ]]; then
    mcCmd=${1}
    mcWorld=${2}
    mcArgs=${@:3}
    sendMinecraftCommand
    echo "Command probably worked"
else
    echo "Error: missing arguments"
fi
