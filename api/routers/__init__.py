from typing import Annotated

from fastapi import Path

IfaceName = Annotated[str, Path(pattern=r"^[a-zA-Z0-9_=+.-]{1,15}$")]
WgKey = Annotated[str, Path(pattern=r"^[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=?$")]
