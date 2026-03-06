# Wiring Guide
This document explains how to wire the electronics for the XY motion platform using an Arduino Uno, A4988 stepper motor drivers, and the Ender-3 power supply.

The system controls two stepper motors (X and Y axes) to create a 2D motion platform.

---

## System Overview

The wiring system consists of three layers:

1. Logic Control (Arduino)
2. Motor Drivers (A4988)
3. Motor Power Supply (Ender-3 PSU)

Architecture:

Arduino -> A4988 drivers -> stepper motors

---

## Required Components

- Arduino Uno
- 2x A4988 stepper motor drivers
- 2x stepper motors (Ender-3)
- Ender-3 24V power supply
- Breadboard
- Jumper wires
- 100 µF capacitor

---

## Logic Wiring (Arduino -> A4988)

The Arduino sends control signals to the stepper drivers

| Arduino Pin | A4988 Pin | Purpose |
|-------------|-----------|--------|
| 5V | VDD | Logic power |
| GND | GND | Logic ground |
| Pin 3 | STEP (Driver X) | X axis step signal |
| Pin 2 | DIR (Driver X) | X axis direction |
| Pin 5 | STEP (Driver Y) | Y axis step signal |
| Pin 6 | DIR (Driver Y) | Y axis direction |

Reset and sleep must be conneced together:

RESET -> SLEEP

This keeps the driver active.

---

## Motor Wiring (A4988 -> Stepper Motor)

Each motor has two coils.

Typical Ender-3 wiring:

Black + Green -> Coil A
Red + Blue -> Coil B

Example connection:

1A -> Black
1B -> Green

2A -> Red
2B -> Blue

If the motor spins in the wrong direction, swap either:

1A ↔1B

or change the DIR signal.

---

## Motor Power Wiring

Stepper motors require a separate power source.

The Ender-3 power supply provides 24V.

Connections:

Ender PSU +24V -> VMOT
Ender PSU GND -> GND

All ground smust be connected together:

Arduino GND
Driver GND
Power Supply GND

---

## Capacitor Requirement

A capacitor must be placed between VMOT and GND near the driver.

VMOT -> capacitor (+)
GND -> capacitor (-)

Recommended value:

100 µF electrolytic capacitor 

This stabilizes voltage spikes and prevents damage to the driver.

---

## Breadboard Layout Concept

Typical layout:

```
Arduino
  │
STEP/DIR signals
  │
[A4988]   [A4988]
   │         │
Motor X   Motor Y
```
Power rails:

```
24V → VMOT rail  
GND → ground rail  
5V → logic rail
```

---

## Safety Notes

Important precautions:
- Never connect or disconnect motors while
- Verify polarity before powering the driver
- Always include the VMOT capacitor
- Ensure all grounds are shared

Incorrect wiring can permanently damage the A4988 driver.

---

## Testing

Testing sequence:

1. Upload Arduino code
2. Power Arduino via USB
3. Verify STEP/DIR signals
4. Connect motor power
5. Test motor movement

---
