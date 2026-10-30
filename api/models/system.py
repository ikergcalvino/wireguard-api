from typing import Literal

from pydantic import BaseModel, Field

CheckResult = Literal["ok", "missing"]


class Info(BaseModel):
    name: str = Field(description="Application name.")
    version: str = Field(description="Application version.")


class Health(BaseModel):
    status: Literal["ok", "degraded"] = Field(description="'degraded' when any check is not 'ok'.")
    checks: dict[str, CheckResult] = Field(
        description="Result of each check: config_dir, wg and wg_quick.",
    )
