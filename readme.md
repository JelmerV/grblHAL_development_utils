# GRBL development utils

Just some scripts to help while working on the scara kinematics for grblHAL.

`setup.sh` clones a hardware driver and puts the forked core in there

`compile_and_copy.sh` will use cmake to build the driver and grbl code, and uploads the compiled firmware to the rpi2040 storage

`test/scara_grbl_visualizer.py` send a simple gcode program to grbl while plotting the scara robot configuration based on the reported joint angles.
![visualizer plot](./scara_visualizer.png)

`test/scara_grbl_interface.py` is a very minimal gui that can send gcode and plot the scara robot. Useful for testing and debugging.

Required config for my setup:

- invert limit switch signals `$14=73`
- invert stepper enable `$4=1`
- set steps per degree `$100=124.4444`, `$101=124.4444`
- set max speeds `$110=500`, `$111=500`
- enable hard limits `$21=1`
- enable homing, allow manual `$22=231`
- set 3 homing passes `$43=3`
- set homing cycle to do X an Y only `$44=3`, `$45=0`
