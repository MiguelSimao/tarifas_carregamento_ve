from enum import Enum

from pydantic import BaseModel, Field


class TariffPeriod(str, Enum):
    PONTA = "ponta"
    CHEIAS = "cheias"
    VAZIO = "vazio"


class TariffCycle(str, Enum):
    DIARIO = "diario"
    SEMANAL = "semanal"


class TariffSchedule(str, Enum):
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
