from enum import Enum

from pydantic import BaseModel


class TariffPeriod(str, Enum):
    PONTA = "ponta"
    CHEIAS = "cheias"
    VAZIO = "vazio"


class TariffCycle(str, Enum):
    DIARIO = "diario"
    SEMANAL = "semanal"


class TarPeriodRate(BaseModel):
    """TAR rate for one time-of-use period."""

    period: TariffPeriod
    rate: float  # €/kWh


class TarVariant(BaseModel):
    """TAR rates for a specific voltage level and cycle."""

    voltage_level: str  # e.g., "BTE", "BTN", "MT"
    cycle: TariffCycle
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
