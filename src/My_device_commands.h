/*
 * Example correctly formatted C header file for command set.
 * My_device_commands.h
 */

#ifndef MY_DEVICE_COMMANDS_H_
#define MY_DEVICE_COMMANDS_H_

// Mixer commands
#define MIXER_START 0x01
#define MIXER_STOP  0x02
// Mixer ack commands
#define MIXER_STARTED 0x81
#define MIXER_STOPPED 0x82


// Display commands
#define DISPLAY_INIT  0x10
#define DISPLAY_CLEAR 0x11
// Display ack commands
#define DISPLAY_READY 0x90
#define DISPLAY_DONE  0x91

#endif     // MY_DEVICE_COMMANDS_H_