#pull RP2040 (or other) driver and submodules:
git clone --recurse-submodules https://github.com/grblHAL/RP2040
mkdir ./RP2040/build

#clone custom grblhal fork
git clone https://github.com/jelmerv/core

#replace normal grblhal core with the custom
rm -r ./RP2040/grbl
#ln -s ./core ./RP2040/grbl
mv ./core ./RP2040/grbl

