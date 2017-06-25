#!/bin/bash

sep="-----------------------------------------------"
echo -e "\nVery basic functionality tests\n$sep"

echo -e "\nSingle\n$sep\n"

meb single -m 928.927 -c 406.4 -v 769.62 -l 35.4617 \
    -f 0.996695 --drag-function KD8 --density-function UK

echo -e "\nMatch Range\n$sep\n"

meb match-range -v 769.62 -m 928.927 -c 406.4 \
    --drag-function KD8 \
    --density-function UK \
    --target-range 15000 \
    -F 15,0.87 20,0.9

echo -e "\nFind Form Factors\n$sep\n"

meb find-ff -m 928.927 -c 406.4 -v 769.62 --drag-function KD8 \
    --density-function UK \
    --shot 2.3,4572 \
           5.1,9144 \
           8.5,13716 \
           12.5,18288 \
           17.5,22860 \
           23.7,27432 \
           32.4,32004 \
           39.2,34290

echo -e "\nRange Table (range increment)\n$sep\n"

meb range-table -m 928.927 -c 406.4 -v 769.62 --drag-function KD8 \
    --density-function UK \
    -F 2.3,0.709893 \
       5.1,0.923971 \
       8.5,0.966435 \
       12.5,0.950629 \
       17.5,0.95898 \
       23.7,0.965627 \
       32.4,0.989613 \
       39.2,1.002287 \
    --start 4572 \
    --end 35000 \
    --increment 4572

echo -e "\nRange Table (angle increment)\n$sep\n"

meb range-table-angle -m 928.927 -c 406.4 -v 769.62 --drag-function KD8 \
    --density-function UK \
    -F 2.3,0.709893 \
       5.1,0.923971 \
       8.5,0.966435 \
       12.5,0.950629 \
       17.5,0.95898 \
       23.7,0.965627 \
       32.4,0.989613 \
       39.2,1.002287 \
    --start 5 \
    --end 45 \
    --increment 5

echo -e "\nMax Range\n$sep\n"

meb max-range -m 928.927 -c 406.4 -v 769.62 --drag-function KD8 \
    --density-function UK \
    -F 2.3,0.709893 \
       5.1,0.923971 \
       8.5,0.966435 \
       12.5,0.950629 \
       17.5,0.95898 \
       23.7,0.965627 \
       32.4,0.989613 \
       39.2,1.002287

echo -e "\n$sep\n"
