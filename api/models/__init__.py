import re

IFACE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_=+.-]{1,15}$")
WG_KEY_PATTERN = re.compile(r"^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=?$")
