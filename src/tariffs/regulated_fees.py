from enum import Enum

from pydantic import AliasChoices, BaseModel, Field


class TariffPeriod(str, Enum):
    PONTA = "ponta"
    CHEIAS = "cheias"
    VAZIO = "vazio"
    FORA_VAZIO = "fora_vazio"


class TariffCycle(str, Enum):
    DIARIO = "diario"
    SEMANAL = "semanal"


class TariffSchedule(str, Enum):
    SIMPLES = "1H"
    BIHORARIO = "2H"
    TRIHORARIO = "3H"


class TarPeriodRate(BaseModel):
    """TAR rate for one time-of-use period."""

    period: TariffPeriod
    rate: float  # €/kWh


class TarVariant(BaseModel):
    """TAR rates for a specific voltage level, schedule (2H/3H/simples), and cycle."""

    voltage_level: str  # e.g., "BTE", "BTN", "MT", "BT"
    schedule: TariffSchedule | None = Field(
        default=None,
        description="Tariff schedule, e.g. '2H' (Bi-horário), '3H' (Tri-horário)",
    )
    cycle: TariffCycle | None = None
    rates: list[TarPeriodRate]


class RegulatedFees(BaseModel):
    """A dated set of regulated fees."""

    country_code: str = "PT"
    effective_date: str
    end_date: str | None = None
    tar_variants: list[TarVariant]
    iec: float  # Electricity special tax (€/kWh)
    egme_connection: float  # EGME/MobiE connection fee
    vat: float | None = None  # VAT rate (e.g. 0.23 for 23%)


class RegulatedFeesDocument(BaseModel):
    """Top-level document for regulated fees YAML files."""

    regulated_fees: list[RegulatedFees]


class TimeRestriction(BaseModel):
    name: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    days_of_week: list[int] | None = None


class TariffCycleSchedule(BaseModel):
    """Time-of-use restrictions definition for a specific cycle, schedule, and date validity range."""

    country_code: str = "PT"
    start_date: str | None = Field(
        default=None,
        validation_alias=AliasChoices("start_date", "effective_date"),
        description="Effective start date of this cycle schedule (YYYY-MM-DD)",
    )
    end_date: str | None = Field(
        default=None,
        description="End date of this cycle schedule (YYYY-MM-DD)",
    )
    cycle: TariffCycle
    schedule: TariffSchedule
    season: str | None = Field(
        default=None,
        description="Seasonal identifier (e.g. 'inverno', 'verao', or None)",
    )
    periods: dict[TariffPeriod, list[TimeRestriction]]


class TimeRestrictionsDocument(BaseModel):
    """Top-level document for time restrictions definition YAML files."""

    time_restrictions_definitions: list[TariffCycleSchedule] = Field(
        validation_alias=AliasChoices("time_restrictions_definitions", "time_restrictions")
    )

