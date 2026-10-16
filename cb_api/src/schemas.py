from enum import StrEnum

from pydantic import BaseModel

from src.analysis import AnalysisTable


class Environment(StrEnum):
    MARINE = "marine"
    TERRESTRIAL = "terrestrial"

    @property
    def table(self) -> AnalysisTable:
        if self is Environment.TERRESTRIAL:
            return AnalysisTable.TERRESTRIAL
        return AnalysisTable.MARINE


class ProtectionLevel(StrEnum):
    FULLY_HIGHLY_PROTECTED = "fully-highly-protected"

    @property
    def table(self) -> AnalysisTable:
        return AnalysisTable.FULLY_HIGHLY_PROTECTED

    @property
    def marine_only(self) -> bool:
        """No protection level has a terrestrial table yet."""
        return True


class Habitat(StrEnum):
    MANGROVES = "mangroves"
    SALTMARSHES = "saltmarshes"
    SEAGRASSES = "seagrasses"
    COLDWATERCORALS = "coldwatercorals"
    CLIMATE_RESILIENT_CORALS = "climate-resilient-corals"
    OTHER_CORALS = "other-corals"

    @property
    def table(self) -> AnalysisTable:
        return AnalysisTable[self.name]


class GeometryRequest(BaseModel):
    """The area to analyse, shared by every endpoint."""

    geometry: dict


class AnalysisRequest(GeometryRequest):
    """Request body for POST /coverage."""

    environment: Environment = Environment.MARINE


class ProtectionLevelRequest(AnalysisRequest):
    """Request body for POST /protection-level."""

    level: ProtectionLevel = ProtectionLevel.FULLY_HIGHLY_PROTECTED


class HabitatRequest(GeometryRequest):
    """Request body for POST /habitats.

    No environment: each habitat has exactly one table.
    """

    habitat: Habitat


class LocationArea(BaseModel):
    code: str
    protected_area: float


class LocationStats(BaseModel):
    """Response body for POST /coverage."""

    locations_area: list[LocationArea]
    total_area: float
    total_protected_area: float
