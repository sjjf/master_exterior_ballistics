#!/bin/bash

function separator {
        echo "-----------------------------------"
}

function header {
        echo -e "\n$1"
        separator
        echo ""
}

function footer {
        echo -e "\n"
        separator
}

header "List all help options"

header "Top level"
meb -h

header "Single Run"
meb single -h

header "Match Range"
meb match-range -h

header "Find Form Factor"
meb find-ff -h

header "Range Table (range increment)"
meb range-table -h

header "Range Table (angle increment)"
meb range-table-angle -h

header "Max Range"
meb max-range -h

header "Make Config"
meb make-config -h

header "GUI command"
meb-gui -h

footer
