from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

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
    SEAMOUNTS = "seamounts"
    COLD_WATER_CORALS = "cold-water-corals"
    CLIMATE_RESILIENT_CORALS = "climate-resilient-corals"
    OTHER_CORALS = "other-corals"

    @property
    def table(self) -> AnalysisTable:
        return AnalysisTable[self.name]


class GeometryRequest(BaseModel):
    """The area to analyze, shared by every endpoint."""

    geometry: dict

    @field_validator("geometry")
    @classmethod
    def _geometry_is_not_empty(cls, value: dict) -> dict:
        """An empty object is treated as no geometry at all."""
        if not value:
            raise ValueError("Geometry is required")
        return value


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


class Location(BaseModel):
    code: str
    added_area: float = Field(
        description="Area of the drawn shape in this location that is not yet protected, in km²"
    )


class LocationStats(BaseModel):
    """Response body for POST /coverage, POST /protection-level and POST /habitats."""

    locations: list[Location]
    total_area: float = Field(description="Area of the drawn shape, in km²")
