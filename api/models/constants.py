import re

RE_IFACE_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,15}$")
RE_WG_KEY = re.compile(r"^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=?$")
