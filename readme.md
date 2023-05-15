# GRBL development utils

Just some scripts to help while working on the custom grblHAL core.

`setup.sh` clones a hardware driver and puts the forked core in there

`compile_and_copy.sh` will use cmake to build the driver and grbl code, and uploads the compiled firmware to the raspberry pi pi storage

`test/scara_grbl_visualizer.py` send a simple gcode program to grbl while plotting the scara robot configuration based on the reported joint angles.
