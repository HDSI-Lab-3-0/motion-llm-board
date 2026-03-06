# Hardware Architecture

This document describes the physical and electrical architecture of the XY motion platform.

The system is designed to convert digital motion commands into physical movement across a 2D plane.

---

## System Components

Core hardware:

- Arduino Uno (control system)
- A4988 stepper motor drivers (motor control)
- CREALITY 42-34 stepper motors (motion)
- Ender-3 24V power supply (power source)
- Breadboard wiring system

Mechanical components:

- XY rail system from Ender-3 printer
- belts and pulleys
- magnet carriage

---

## System Layers

The hardware system can be divided into three layers.

### Control Layer

The Arduino is responsible for generating step and direction signals.

Functions:
- send step pulses
- control motor direction
- coordinate movement

---

### Driver Layer

The A4988 drivers convert control signals into motor current.

Responsibilities:

- translate step pulses into coil switching
- control current through motor coils
- enable microstepping

Each axis has its own driver.

```
Driver X -> controls X axis motor
Driver Y -> controls Y axis motor
```
---

### Motion Layer

The stepper motors convert electrical signals into mechanical rotation.

Motors drive:
- belt systems
- linear rails

These rails produce the XY motion platform.

---

## Power Architecture

Two independent power domains exist.

### Logic Power

Provided by the Arduino

Voltage:

5V 

Used for:
- A4988 logic control
- step and direction signals

--- 

### Motor Power

Provided by the Ender-3 PSU.

Voltage:

24V

Used for:
- stepper motor coils

Connection path:

```
Power Supply -> VMOT -> Driver -> Motor
```

## Signal Flow
Movement commands follow this path:

```
Computer / code  
↓  
Arduino firmware  
↓  
STEP / DIR signals  
↓  
A4988 driver  
↓  
Stepper motor rotation  
↓  
Belt movement  
↓  
XY platform motion
```

---

## Coordinate System

The platform operates in a 2D coordinate space.

Example coordinate grid:
```
(0,0) = home position
```
Each letter or target location can be mapped to coordinates:
```
A -> (x1, y1)
B -> (x2, y2)
YES -> (x3, y3)
```

This allows software to convert text output into physical movement.


