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


class Location(BaseModel):
    code: str
    added_area: float = Field(
        description="Area of the drawn shape in this location that is not yet protected, in km²"
    )


class LocationStats(BaseModel):
    """Response body for POST /coverage."""

    locations: list[Location]
    total_area: float = Field(description="Area of the drawn shape, in km²")
