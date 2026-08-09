from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DimensionType(str, Enum):
    ENERGY = "energy"
    TIME = "time"
    FLAT = "flat"
    PARKING = "parking"


class PaymentMethod(str, Enum):
    ADHOC = "ADHOC"
    ADHOC_BANK_CARD = "ADHOC_BANK_CARD"
    RFID_CARD = "RFID_CARD"
    APP = "APP"


class TimeRestriction(BaseModel):
    start_time: str | None = None
    end_time: str | None = None
    days_of_week: list[int] | None = None


class TariffTier(BaseModel):
    min: float | None = None
    max: float | None = None
    price: float
    unit: DimensionType | None = None
    start_after: float | None = Field(
        default=None,
        description="Threshold offset / grace period in minutes before the fee applies",
    )


class Tariff(BaseModel):
    type: Literal["AC", "DC"] | None = None
    price: float | None = None
    unit: DimensionType = DimensionType.ENERGY
    min: float | None = None
    max: float | None = None
    start_after: float | None = Field(
        default=None,
        description="Threshold offset / grace period in minutes before the fee applies",
    )
    tiers: list[TariffTier] | None = None
    time_restrictions: list[TimeRestriction] | None = None

    @model_validator(mode="after")
    def validate_and_propagate_tariff(self) -> "Tariff":
        if self.price is None and self.tiers is None:
            raise ValueError('Either "price" or "tiers" must be provided in a tariff')
        if self.price is not None and self.tiers is not None:
            raise ValueError('Cannot specify both "price" and "tiers" in a tariff')

        if self.tiers:
            for tier in self.tiers:
                if tier.unit is None:
                    tier.unit = self.unit
                if tier.start_after is None and self.start_after is not None:
                    tier.start_after = self.start_after
            if self.start_after is not None:
                self.start_after = None
        return self


class Network(BaseModel):
    network_id: str
    display_name: str | None = None
    cashback: float | None = None
    included_cpos: list[str] | None = None
    excluded_cpos: list[str] | None = None
    included_locations: list[str] | None = None
    excluded_locations: list[str] | None = None
    tariffs: list[Tariff]


class Plan(BaseModel):
    name: str
    country_code: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    cost: float | None = None
    months: int | None = None
    period: str | None = None
    payment_methods: list[PaymentMethod] | None = None
    networks: list[Network]


class Provider(BaseModel):
    name: str
    plans: list[Plan]


class TariffDocument(BaseModel):
    providers: list[Provider]


class Connector(BaseModel):
    id: str
    type: Literal["AC", "DC"]
    max_power_kw: float


class Location(BaseModel):
    id: str
    cpo_name: str
    network_name: str = "MOBIE"
    connectors: list[Connector]
