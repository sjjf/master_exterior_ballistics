#!/bin/bash

echo -e "\nVery basic functionality tests\n"

echo -e "\nSingle\n-----------------------------------------------\n"

meb single -m 952.544 -c 406.4 -v 792.48 -l 35.4617 \
    -f 0.996695 --drag-function KD6

echo -e "\nMatch Range\n-----------------------------------------------\n"

meb match-range -v 769.62 -m 928.927 -c 406.4 \
    --drag-function KD6 --target-range 15000 \
    -F 15,0.87 -F 20,0.9

echo -e "\nFind Form Factors\n-----------------------------------------------\n"

meb find-ff -m 928.927 -c 406.4 -v 769.62 --drag-function KD2 \
    --density-function UK \
    --shot 2.3,4572 \
    --shot 5.1,9144 \
    --shot 8.5,13716 \
    --shot 12.5,18288 \
    --shot 17.5,22860 \
    --shot 23.7,27432 \
    --shot 32.4,32004 \
    --shot 39.2,34290

echo -e "\nRange Table (range increment)\n-----------------------------------------------\n"

meb range-table -m 928.927 -c 406.4 -v 769.62 --drag-function KD8 \
    --density-function UK \
    -F 2.3,0.709893 \
    -F 5.1,0.923971 \
    -F 8.5,0.966435 \
    -F 12.5,0.950629 \
    -F 17.5,0.95898 \
    -F 23.7,0.965627 \
    -F 32.4,0.989613 \
    -F 39.2,1.002287 \
    --start 4572 \
    --end 35000 \
    --increment 4572

echo -e "\nRange Table (angle increment)\n-----------------------------------------------\n"

meb range-table-angle -m 928.927 -c 406.4 -v 769.62 --drag-function KD8 \
    --density-function UK \
    -F 2.3,0.709893 \
    -F 5.1,0.923971 \
    -F 8.5,0.966435 \
    -F 12.5,0.950629 \
    -F 17.5,0.95898 \
    -F 23.7,0.965627 \
    -F 32.4,0.989613 \
    -F 39.2,1.002287 \
    --start 5 \
    --end 45 \
    --increment 5

echo -e "\nMax Range\n-----------------------------------------------\n"

meb max-range -m 928.927 -c 406.4 -v 769.62 --drag-function KD8 \
    --density-function UK \
    -F 2.3,0.709893 \
    -F 5.1,0.923971 \
    -F 8.5,0.966435 \
    -F 12.5,0.950629 \
    -F 17.5,0.95898 \
    -F 23.7,0.965627 \
    -F 32.4,0.989613 \
    -F 39.2,1.002287

echo -e "\n-----------------------------------------------\n"
