from enum import Enum
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from .regulated_fees import RegulatedFees, TariffPeriod, TariffSchedule


class MobieVoltageLevel(str, Enum):
    BT = "BT"
    MT = "MT"
    BTE = "BTE"
    BTN = "BTN"
    AT = "AT"
    MAT = "MAT"


class MobieFeeType(str, Enum):
    CEME = "CEME"
    EGME = "EGME"
    TAR = "TAR"
    IEC = "IEC"


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
    mobie_fee_type: MobieFeeType | None = None
    mobie_voltage_level: MobieVoltageLevel | None = None
    min: float | None = None
    max: float | None = None
    start_after: float | None = Field(
        default=None,
        description="Threshold offset / grace period in minutes before the fee applies",
    )
    tiers: list[TariffTier] | None = None
    time_restrictions: list[TimeRestriction] | None = None
    tou_period: TariffPeriod | None = None

    @field_validator("tou_period", mode="before")
    @classmethod
    def parse_tou_period(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

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
    tariffs: list[Tariff] = Field(default_factory=list)


class ByoeConfig(BaseModel):
    start_date: str | None = None
    cycle: Literal["diario", "semanal"] | None = None
    schedule: TariffSchedule | None = Field(
        default=None,
        description="Tariff schedule, e.g. '2H' (Bi-horário), '3H' (Tri-horário)",
    )
    includes_tar: bool | None = None
    includes_iec: bool | None = None
    includes_egme: bool | None = None
    activation_fee: float | None = None
    opc_commission_pct: float | None = None
    renewable_energy: bool | None = None

    # TOU rate prices
    vazio: float | None = None
    cheias: float | None = None
    fora_vazio: float | None = None
    ponta: float | None = None

    # Further restritions
    power_type: Literal["AC", "DC"] | None = Field(
        default=None,
        validation_alias=AliasChoices("power_type", "type"),
        description="Power/current type restriction: AC or DC",
    )

    @model_validator(mode="after")
    def validate_byoe_rates(self) -> "ByoeConfig":
        if self.schedule == TariffSchedule.BIHORARIO:
            if self.ponta is not None:
                raise ValueError("Schedule '2H' does not support 'ponta' rate.")
            if self.cheias is not None:
                if self.fora_vazio is None:
                    self.fora_vazio = self.cheias
                self.cheias = None
        return self


class Plan(BaseModel):
    name: str
    country_code: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    cost: float | None = None
    months: int | None = None
    period: str | None = None
    payment_methods: list[PaymentMethod] | None = None
    includes_vat: bool | None = Field(
        default=None,
        validation_alias=AliasChoices("includes_vat", "vat_included"),
        description="Whether VAT (IVA) is included in the plan prices",
    )
    contract_conditions: list[ContractCondition] | None = Field(
        default=None,
        validation_alias=AliasChoices("contract_conditions", "conditions"),
        description="Collection of contract conditions required for the plan",
    )
    notes: list[DisplayText] | None = Field(
        default=None,
        description="Collection of notes for the plan in various languages",
    )
    byoe: ByoeConfig | None = Field(
        default=None,
        description="BYOE (CEME) specifics. If omitted or null, the plan is treated as a standard plan.",
    )
    networks: list[Network] = Field(default_factory=list)

    @property
    def is_byoe(self) -> bool:
        return self.byoe is not None

    @field_validator("byoe", mode="before")
    @classmethod
    def parse_byoe(cls, v):
        if isinstance(v, bool):
            return {} if v else None
        return v

    @field_validator("notes", mode="before")
    @classmethod
    def parse_notes(cls, v):
        if isinstance(v, str):
            return [{"language": "pt", "text": v}]
        if isinstance(v, dict):
            return [v]
        return v

    @model_validator(mode="after")
    def validate_plan_tariffs(self) -> "Plan":
        if not self.is_byoe:
            for network in self.networks or []:
                for tariff in network.tariffs or []:
                    if tariff.mobie_fee_type is not None:
                        raise ValueError(
                            f"Plan '{self.name}' is not a BYOE plan, but defines tariff with mobie_fee_type '{tariff.mobie_fee_type.value if hasattr(tariff.mobie_fee_type, 'value') else tariff.mobie_fee_type}'."
                        )
        schedule = self.byoe.schedule if self.byoe else None
        if schedule == TariffSchedule.BIHORARIO:
            for network in self.networks or []:
                for tariff in network.tariffs or []:
                    if tariff.tou_period is not None:
                        if tariff.tou_period == TariffPeriod.CHEIAS:
                            tariff.tou_period = TariffPeriod.FORA_VAZIO
                        elif tariff.tou_period not in (
                            TariffPeriod.VAZIO,
                            TariffPeriod.FORA_VAZIO,
                        ):
                            raise ValueError(
                                f"Invalid tou_period '{tariff.tou_period.value}' for schedule '2H'. "
                                f"Allowed periods are '{TariffPeriod.VAZIO.value}' and '{TariffPeriod.FORA_VAZIO.value}' "
                                f"(or '{TariffPeriod.CHEIAS.value}' mapped to '{TariffPeriod.FORA_VAZIO.value}')."
                            )
        return self


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
