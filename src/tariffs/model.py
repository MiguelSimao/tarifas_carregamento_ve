from enum import Enum
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from .regulated_fees import RegulatedFees, TariffPeriod, TariffSchedule, TimeRestriction


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
    CPO_TOTAL = "CPO_TOTAL"
    CEME_TOTAL = "CEME_TOTAL"
    TOTAL = "TOTAL"


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
    byoe: bool | None = Field(
        default=None,
        description="Placeholder indicator for BYOE tariff expansion",
    )

    @property
    def is_byoe_placeholder(self) -> bool:
        return bool(self.byoe)

    @field_validator("tou_period", mode="before")
    @classmethod
    def parse_tou_period(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

    @model_validator(mode="after")
    def validate_and_propagate_tariff(self) -> "Tariff":
        if not self.is_byoe_placeholder and self.price is None and self.tiers is None:
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


class Discount(BaseModel):
    percentage: float | None = Field(
        default=None,
        description="Percentage discount as a decimal (e.g. 0.20 for 20%)",
    )
    flat: float | None = Field(
        default=None,
        description="Flat discount amount per kWh (e.g. 0.02 for 0.02 €/kWh)",
    )
    cashback: bool = Field(
        default=False,
        description="True if refunded as cashback/credit; False if applied directly to price",
    )
    applies_to: MobieFeeType | None = Field(
        default=MobieFeeType.CEME,
        description="Mobi.E fee component the discount applies to (e.g. CEME, TAR, EGME, IEC). Defaults to CEME.",
    )

    @model_validator(mode="before")
    @classmethod
    def parse_number_or_dict(cls, value):
        if isinstance(value, (int, float)):
            return {"percentage": float(value)}
        return value

    @property
    def effective_percentage(self) -> float | None:
        """Calculate effective percentage discount rate. For cashback, effective rate is x / (1 + x)."""
        if self.percentage is None:
            return None
        if self.cashback:
            return self.percentage / (1.0 + self.percentage)
        return self.percentage

    @model_validator(mode="after")
    def validate_discount_values(self) -> "Discount":
        if self.percentage is None and self.flat is None:
            raise ValueError('Either "percentage" or "flat" must be specified for a discount.')
        if self.percentage is not None and self.flat is not None:
            raise ValueError('Cannot specify both "percentage" and "flat" in the same discount.')
        return self


class Network(BaseModel):
    network_id: str
    display_name: str | None = None
    discount: Discount | None = Field(
        default=None,
        description="Discount/cashback configuration for the network",
    )
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
    includes_vat: bool = Field(
        default=False,
        validation_alias=AliasChoices("includes_vat", "vat_included"),
        description="Whether VAT (IVA) is included in the BYOE rates",
    )
    includes_tar: bool | None = None
    includes_iec: bool | None = None
    includes_egme: bool | None = None
    activation_fee: float | None = None
    opc_commission_pct: float | None = None
    renewable_energy: bool | None = None

    # TOU / single rate prices
    all_day: float | None = None
    vazio: float | None = None
    cheias: float | None = None
    fora_vazio: float | None = None
    ponta: float | None = None

    @model_validator(mode="after")
    def validate_byoe_rates(self) -> "ByoeConfig":
        if self.schedule == TariffSchedule.BIHORARIO:
            if self.ponta is not None:
                raise ValueError("Schedule '2H' does not support 'ponta' rate.")
            if self.cheias is not None:
                if self.fora_vazio is None:
                    self.fora_vazio = self.cheias
                self.cheias = None
        elif self.schedule == TariffSchedule.SIMPLES:
            if self.ponta is not None:
                raise ValueError("Schedule '1H' does not support 'ponta' rate.")
            if self.vazio is not None and self.cheias is not None and self.vazio != self.cheias:
                raise ValueError("Schedule '1H' requires a single rate (use 'all_day').")
            if self.all_day is None:
                if self.fora_vazio is not None:
                    self.all_day = self.fora_vazio
                elif self.cheias is not None:
                    self.all_day = self.cheias
                elif self.vazio is not None:
                    self.all_day = self.vazio
            self.cheias = None
            self.vazio = None
            self.fora_vazio = None
        return self


class Plan(BaseModel):
    name: str
    publish: bool = Field(
        default=True,
        description="Whether this plan should be published and included in compilation",
    )
    country_code: str | None = None
    regions: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices("regions", "applicable_regions"),
        description="List of regional country codes where this plan is applicable (e.g. ['PT', 'PT::RAA', 'PT::RAM'])",
    )
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
    vat: float | None = Field(
        default=None,
        validation_alias=AliasChoices("vat", "vat_rate"),
        description="Applicable VAT rate for the plan and region (e.g. 0.23 for 23%, 0.16 for 16%, 0.22 for 22%)",
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
                    if tariff.is_byoe_placeholder:
                        raise ValueError(
                            f"Plan '{self.name}' is not a BYOE plan, but defines tariff with byoe placeholder."
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
    publish: bool = Field(
        default=True,
        description="Whether this provider should be published and included in compilation",
    )
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
