from enum import Enum
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


from .regulated_fees import RegulatedFees, TariffPeriod


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


class ContractCondition(str, Enum):
    ENERGY_AT_HOME = "ENERGY_AT_HOME"
    PARTNERSHIP = "PARTNERSHIP"
    APP_ACTIVATION = "APP_ACTIVATION"
    CARD_ACTIVATION = "CARD_ACTIVATION"
    DIRECT_DEBIT = "DIRECT_DEBIT"
    ELECTRONIC_INVOICE = "ELECTRONIC_INVOICE"
    LOYALTY_PROGRAM = "LOYALTY_PROGRAM"
    EV_OWNERSHIP = "EV_OWNERSHIP"


class AppType(str, Enum):
    WEB = "web"
    ANDROID = "android"
    IOS = "ios"


class AppUrl(BaseModel):
    web: str | None = None
    android: str | None = None
    ios: str | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_str_or_dict(cls, value):
        if isinstance(value, str):
            return {"web": value}
        return value


class DisplayText(BaseModel):
    language: str
    text: str


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
    tou_period: TariffPeriod | None = None

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
    byoe: bool = False
    country_code: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    cost: float | None = None
    months: int | None = None
    period: str | None = None
    payment_methods: list[PaymentMethod] | None = None
    cycle: Literal["diario", "semanal"] | None = None
    includes_vat: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("includes_vat", "vat_included"),
        description="Whether VAT (IVA) is included in the plan prices",
    )
    includes_tar: bool | None = None
    includes_iec: bool | None = None
    includes_egme: bool | None = None
    activation_fee: float | None = None
    opc_commission_pct: float | None = None
    renewable_energy: bool | None = None
    contract_conditions: list[ContractCondition] | None = Field(
        default=None,
        validation_alias=AliasChoices("contract_conditions", "conditions"),
        description="Collection of contract conditions required for the plan",
    )
    notes: list[DisplayText] | None = Field(
        default=None,
        description="Collection of notes for the plan in various languages",
    )
    networks: list[Network]

    @field_validator("notes", mode="before")
    @classmethod
    def parse_notes(cls, v):
        if isinstance(v, str):
            return [{"language": "pt", "text": v}]
        if isinstance(v, dict):
            return [v]
        return v


class Provider(BaseModel):
    name: str
    url: str | None = None
    app_url: AppUrl | None = Field(
        default=None,
        validation_alias=AliasChoices("app_url", "app_urls"),
        description="Provider application URLs (web, android, ios)",
    )
    updated_at: str | None = None
    plans: list[Plan]


class TariffDocument(BaseModel):
    providers: list[Provider]
    regulated_fees: list[RegulatedFees] | None = None


class Connector(BaseModel):
    id: str
    type: Literal["AC", "DC"]
    max_power_kw: float


class Location(BaseModel):
    id: str
    cpo_name: str
    network_name: str = "MOBIE"
    connectors: list[Connector]
