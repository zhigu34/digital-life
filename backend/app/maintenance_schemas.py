from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.schemas import ISODate, Notes, Payload, StrictBool, StrictInt, patch_schema


class MaintenanceConfig(Payload):
    title: Annotated[str, Field(min_length=1, max_length=120)]
    notes: Notes = ""
    period_value: Annotated[StrictInt, Field(ge=1, le=3650)]
    period_unit: Literal["days", "months"]
    remind_days: Annotated[StrictInt, Field(ge=0, le=365)] = 7
    active: StrictBool = True

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_unit == "months" and self.period_value > 120:
            raise ValueError("Monthly period cannot exceed 120 months")
        return self


class MaintenanceCreate(MaintenanceConfig):
    last_completed: ISODate


class MaintenanceView(MaintenanceCreate):
    id: int
    next_due: ISODate


class MaintenanceCompletion(Payload):
    completed_on: ISODate
    notes: Notes = ""
    cost_cents: Annotated[StrictInt, Field(ge=0, le=100000000)] | None = None
    currency: Literal["CNY", "USD", "EUR", "JPY", "HKD"] = "CNY"


class MaintenanceLogView(MaintenanceCompletion):
    id: int
    maintenance_id: int
    created_at: datetime


MaintenancePatch = patch_schema("MaintenancePatch", MaintenanceConfig)
MaintenanceLogPatch = patch_schema("MaintenanceLogPatch", MaintenanceCompletion)
