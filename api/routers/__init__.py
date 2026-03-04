from typing import Annotated

from fastapi import Path

from api.models import IFACE_NAME_PATTERN, WG_KEY_PATTERN

IfaceName = Annotated[str, Path(pattern=IFACE_NAME_PATTERN.pattern)]
WgKey = Annotated[str, Path(pattern=WG_KEY_PATTERN.pattern)]
