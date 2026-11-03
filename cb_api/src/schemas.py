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


class AnalysisRequest(BaseModel):
    """Request body for POST /coverage."""

    geometry: dict
    environment: Environment = Environment.MARINE

    @field_validator("geometry")
    @classmethod
    def _geometry_is_not_empty(cls, value: dict) -> dict:
        """An empty object is treated as no geometry at all."""
        if not value:
            raise ValueError("Geometry is required")
        return value


class ProtectionLevelRequest(AnalysisRequest):
    """Request body for POST /protection-level."""

    level: ProtectionLevel = ProtectionLevel.FULLY_HIGHLY_PROTECTED


class LocationArea(BaseModel):
    code: str
    added_area: float = Field(
        description="Area of the drawn shape in this location that is not yet protected, in km²"
    )


class LocationStats(BaseModel):
    """Response body for POST /coverage."""

    locations_area: list[LocationArea]
    total_area: float = Field(description="Area of the drawn shape, in km²")
