# Stepper Motor Setup

This document explains how the stepper motors are configured and controlled.

The system uses CREALITY 42-34(Z) stepper motors from the Ender-3 3D printer.

---

## Stepper Motor Basics

Stepper motors rotate in discrete steps.

Each step corresponds to a small angular movement.

Typical step resolution:

200 steps per revolution

This means:

1.8° per step

---

## Coil Structure

Stepper motors contain two internal coils.

Coil A
Coil B

Each coil must be connected to the correct driver outputs.

Driver pins:
```
1A -> Coil A
1B -> Coil A

2A -> Coil B
2B -> Coil B

---

## Typical Ender-3 Motor Wiring
Wire colors:

Black + Green -> Coil A
Red + Blue -> Coil B

Example wiring:
```
1A -> Black
1B -> Green

2A -> Red
2B -> Blue
```

---

## Direction Control

Motor diretion is controlled by the DIR signal.

```
DIR HIGH -> one direction
DIR LOW -> opposite direction
```

If motion appears reversed:

Swap
```
1A ↔ 1B

or

change DIR logic in software.
```

---

## Step Signal

Motor movement occurs when a pulse is sent to the STEP pin.

Example:
```
HIGH -> LOW transition = one step
```

Pseudo-code:
```
digitalWrite(STEP, HIGH)
digitalWrite(STEP, LOW)
```

Each pulse advances the motor one step.

---

## Microstepping

The A4988 supports microstepping.

Possible settings:

Full step
Half step
Quarter step
Eighth step
Sixteenth step

Microstepping increases motion smoothness.

Microstepping is configured using pins:

MS1
MS2
MS3

If these pins are left unconnected:
Driver defaults to full-step mode.

---

## Motor Speed

Motor speed depends on pulse frequency.

Higher pulse frequency = faster rotation.

Speed control example:
```
delayMicroseconds()
```

Shorter delay -> faster movement.

---

## Motor Testing

Basic test procedure:

1. Connect STEP and DIR pins
2. Upload motor test code
3. Send repeated step pulses
4. Observe motor rotation

If motor vibrates but does not rotate:

- coil wiring is incorrect
- power supply is missing
- current limit is too low

---

## Current Limiting

The A4988 includes a current limiting potentiometer

This must be adjusted to match the motor.

Incorrect current settings may cause:

- overheating
- missed steps
- motor vibration

Adjustment should be performed carefully with a multimeter.

---
