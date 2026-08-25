from enum import Enum

from pydantic import AliasChoices, BaseModel, Field, model_validator


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
    effective_date: str = Field(
        validation_alias=AliasChoices("effective_date", "effective_start_date"),
        description="Effective start date of this regulation period (YYYY-MM-DD)",
    )
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
    """Time-of-use restrictions definition for a specific cycle, schedule, and seasonal date validity range."""

    cycle: TariffCycle
    schedule: TariffSchedule
    season: str | None = Field(
        default=None,
        description="Seasonal identifier (e.g. 'inverno', 'verao', or None)",
    )
    start_date: str | None = Field(
        default=None,
        description="Seasonal start date (YYYY-MM-DD)",
    )
    end_date: str | None = Field(
        default=None,
        description="Seasonal end date (YYYY-MM-DD)",
    )
    periods: dict[TariffPeriod, list[TimeRestriction]]
    country_code: str = "PT"
    effective_start_date: str | None = Field(
        default=None,
        validation_alias=AliasChoices("effective_start_date", "effective_date"),
        description="Effective start date of this regulation period (YYYY-MM-DD)",
    )


class RegulationTimeRestrictions(BaseModel):
    """A set of time-of-use restriction schedules for a country/region and regulation period."""

    country_code: str = "PT"
    effective_start_date: str = Field(
        validation_alias=AliasChoices("effective_start_date", "effective_date", "start_date"),
        description="Effective start date of this regulation period (YYYY-MM-DD)",
    )
    end_date: str | None = Field(
        default=None,
        description="End date of this regulation period (YYYY-MM-DD)",
    )
    schedules: list[TariffCycleSchedule]

    @model_validator(mode="after")
    def propagate_metadata(self) -> "RegulationTimeRestrictions":
        for s in self.schedules:
            if not s.country_code or s.country_code == "PT":
                s.country_code = self.country_code
            if not s.effective_start_date:
                s.effective_start_date = self.effective_start_date
        return self


class TimeRestrictionsDocument(BaseModel):
    """Top-level document for time restrictions definition YAML files."""

    time_restrictions: list[RegulationTimeRestrictions] = Field(
        validation_alias=AliasChoices("time_restrictions", "time_restrictions_definitions")
    )

    @property
    def time_restrictions_definitions(self) -> list[TariffCycleSchedule]:
        """Convenience accessor returning all flattened TariffCycleSchedule instances."""
        all_schedules: list[TariffCycleSchedule] = []
        for reg in self.time_restrictions:
            all_schedules.extend(reg.schedules)
        return all_schedules

