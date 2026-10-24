"""Constants for the RD30 integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

DOMAIN = "rd30"

DEFAULT_PORT = 4001

# Protocol bytes (AK MODUL-BUS RD30 datasheet).
# The device pushes one byte per input change:
#   input switched ON : 128 + input number  (129..158)
#   input switched OFF:  64 + input number  ( 65.. 94)
# Query commands, each answered with a single byte:
CMD_IDENTIFY = 1          # answered with 30
IDENTIFY_REPLY = 30
CMD_QUERY = {32: 1, 33: 9, 34: 17, 35: 25}  # command -> first input number

EVENT_ON_BASE = 128
EVENT_OFF_BASE = 64
NUM_INPUTS = 30

# Full resync interval, seconds.  Two jobs: it heals a lost event byte, and
# because the queries must be answered within 2 s it is also the watchdog
# that detects a half-open TCP session.  So it doubles as the upper bound on
# how long a safety-relevant input (water detector) can stay blind — worth
# more than the five bytes per minute it costs.
RESYNC_INTERVAL = 60

# Reconnect backoff bounds, seconds.
RECONNECT_MIN = 5
RECONNECT_MAX = 60

# Options: per-input settings, keyed by the input number as a string
# (JSON keys are strings).  {"inputs": {"26": {"name": "...", "device_class": "moisture"}}}
CONF_INPUTS = "inputs"
CONF_INPUT = "input"
CONF_NAME = "name"
CONF_DEVICE_CLASS = "device_class"
CONF_RESET = "reset"
DEVICE_CLASS_NONE = "none"

# Device classes that make sense for a dry contact / opto input.
INPUT_DEVICE_CLASSES: list[str] = [
    DEVICE_CLASS_NONE,
    BinarySensorDeviceClass.BATTERY,
    BinarySensorDeviceClass.COLD,
    BinarySensorDeviceClass.CONNECTIVITY,
    BinarySensorDeviceClass.DOOR,
    BinarySensorDeviceClass.GARAGE_DOOR,
    BinarySensorDeviceClass.GAS,
    BinarySensorDeviceClass.HEAT,
    BinarySensorDeviceClass.LIGHT,
    BinarySensorDeviceClass.LOCK,
    BinarySensorDeviceClass.MOISTURE,
    BinarySensorDeviceClass.MOTION,
    BinarySensorDeviceClass.MOVING,
    BinarySensorDeviceClass.OCCUPANCY,
    BinarySensorDeviceClass.OPENING,
    BinarySensorDeviceClass.PLUG,
    BinarySensorDeviceClass.POWER,
    BinarySensorDeviceClass.PRESENCE,
    BinarySensorDeviceClass.PROBLEM,
    BinarySensorDeviceClass.RUNNING,
    BinarySensorDeviceClass.SAFETY,
    BinarySensorDeviceClass.SMOKE,
    BinarySensorDeviceClass.SOUND,
    BinarySensorDeviceClass.TAMPER,
    BinarySensorDeviceClass.VIBRATION,
    BinarySensorDeviceClass.WINDOW,
]


def input_options(options: dict, number: int) -> dict:
    """Settings of one input from the entry options (empty dict if none)."""
    return (options.get(CONF_INPUTS) or {}).get(str(number)) or {}
