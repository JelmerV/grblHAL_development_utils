#!/bin/bash

cd ./RP2040/build

echo building
cmake ..
make -j$(nproc)

echo copying to RPI
cp grblHAL.uf2 /media/jelmer/RPI-RP2/
sync
