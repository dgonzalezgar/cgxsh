DEFAULT_YAML_WITH_COMMENTS = b"""---
type: cgxsh
version: 1.0

# This section allows you to specify a default AUTH_TOKEN, DEVICE_USER and DEVICE_PASSWORD. These will be used
# by default if others are not specified.
#
# For Controller authentication, AUTH_TOKEN is used first (if present.) If no AUTH_TOKEN, CONTROLLER_USER and 
# CONTROLLER_PASSWORD are used. If those are missing or fail, login will be prompted.
# 
# If the DEVICE_USER or DEVICE_PASSWORD fails, you will be prompted to finish logging in when connecting to the device.

DEFAULT:
    AUTH_TOKEN:
    CONTROLLER_USER:
    CONTROLLER_PASSWORD:
    DEVICE_USER: 
    DEVICE_PASSWORD: 

# If you have a CloudGenix MSP/ESP portal account, you can specify the device access credentials on a per-client
# basis. If the client name is not an exact match, the credentials will not be used.
#
# Note: MSP/ESP client attachment requires DEFAULT: CONTROLLER_USERNAME/CONTROLLER_PASSOWRD. AUTH_TOKENs cannot be used. 

ESP:
  "Example Client1 Name Match":
    DEVICE_USER:
    DEVICE_PASSWORD: 
    
  "Example Client2 Name Match":
    DEVICE_USER:
    DEVICE_PASSWORD: 
"""

DEFAULT_CONTROL_CHAR_DICT = {
    '\0': '^@',  # Null character
    '\1': '^A',  # Start of heading
    '\2': '^B',  # Start of text
    '\3': '^C',  # End of text
    '\4': '^D',  # End of transmission
    '\5': '^E',  # Enquiry
    '\6': '^F',  # Acknowledge
    '\a': '^G',  # Audible bell
    '\b': '^H',  # Backspace
    '\t': '^I',  # Horizontal tab
    '\n': '^J',  # Line feed
    '\v': '^K',  # Vertical tab
    '\f': '^L',  # Form feed
    '\r': '^M',  # Carriage return
    '\x0e': '^N',  # Shift out
    '\x0f': '^O',  # Shift in
    '\x10': '^P',  # Data link escape
    '\x11': '^Q',  # Device control 1
    '\x12': '^R',  # Device control 2
    '\x13': '^S',  # Device control 3
    '\x14': '^T',  # Device control 4
    '\x15': '^U',  # Negative Acknowledge
    '\x16': '^V',  # Synchronous idle
    '\x17': '^W',  # End of transmission block
    '\x18': '^X',  # Cancel
    '\x19': '^Y',  # End of medium
    '\x1a': '^Z',  # Substitute
    '\x1b': '^[',  # Escape
    '\x1c': '^\\',  # File separator
    '\x1d': '^]',  # Group separator
    '\x1e': '^^',  # Record separator
    '\x1f': '^-',  # Unit separator
}
