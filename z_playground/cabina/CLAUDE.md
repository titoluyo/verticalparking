# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Arduino/embedded project for a cabin sensor system, likely part of a vertical parking system. The main code is in `cabina.ino` which controls WS2812 LED strips using the FastLED library.

## Code Architecture

- **Main sketch**: `cabina.ino` - Contains the main Arduino loop that cycles through RGB colors on a WS2812 LED
- **Hardware configuration**:
  - Uses GPIO pin 48 for WS2812 LED data
  - Serial communication at 9600 baud
  - Single LED configuration
- **Dependencies**: FastLED library for WS2812/NeoPixel LED control

## Development Workflow

This appears to be a standard Arduino project without automated build tools. Development would typically be done through:

1. Arduino IDE
2. PlatformIO
3. Or manual compilation with arduino-cli

Since no build configuration files (platformio.ini, Makefile, etc.) are present, this project likely uses the Arduino IDE for compilation and upload.

## Hardware Context

Based on the project structure and naming (verticalparking/cabinasensor), this is sensor hardware for a vertical parking system cabin, using LED indicators for status display.