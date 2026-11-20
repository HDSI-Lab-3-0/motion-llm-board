"""Raspberry Pi LED for the Ouijai listener status."""

import os


class StatusLed:
    """Drive one active-high LED, or safely do nothing off-Pi."""

    def __init__(self, pin=None):
        self.pin = int(pin or os.getenv("OUIJA_STATUS_LED_GPIO", "17"))
        self._gpio = None

        enabled = os.getenv("OUIJA_STATUS_LED_ENABLED", "true").lower()
        if enabled not in {"1", "true", "yes", "on"}:
            return

        try:
            import RPi.GPIO as GPIO
        except (ImportError, RuntimeError):
            # Expected during local development and in unit tests.
            return

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT, initial=GPIO.LOW)
        self._gpio = GPIO

    @property
    def available(self):
        return self._gpio is not None

    def set_on(self, on):
        if self._gpio is not None:
            self._gpio.output(self.pin, self._gpio.HIGH if on else self._gpio.LOW)

    def set_status(self, status):
        """Turn on only when the board can accept a spoken question."""
        self.set_on(str(status).upper() in {"READY", "LISTENING"})

    def close(self):
        self.set_on(False)
        if self._gpio is not None:
            self._gpio.cleanup(self.pin)
            self._gpio = None


def create_status_led():
    """Create the configured LED without failing on non-Raspberry Pi hosts."""
    return StatusLed()
