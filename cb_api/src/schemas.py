from enum import StrEnum

from pydantic import BaseModel, field_validator

from src.analysis import AnalysisTable


class Environment(StrEnum):
    MARINE = "marine"
    TERRESTRIAL = "terrestrial"

    @property
    def table(self) -> AnalysisTable:
        if self is Environment.TERRESTRIAL:
            return AnalysisTable.TERRESTRIAL
        return AnalysisTable.MARINE


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


class LocationArea(BaseModel):
    code: str
    protected_area: float


class LocationStats(BaseModel):
    """Response body for POST /coverage."""

    locations_area: list[LocationArea]
    total_area: float
    total_protected_area: float
