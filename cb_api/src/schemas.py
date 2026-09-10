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


class Stat(StrEnum):
    """Optional extra statistics a request can ask for."""

    FULLY_HIGHLY_PROTECTED = "fully-highly-protected"


class AnalysisRequest(BaseModel):
    """Request body for POST /."""

    geometry: dict
    environment: Environment = Environment.MARINE
    stats: list[Stat] = Field(default_factory=list)

    @field_validator("stats", mode="before")
    @classmethod
    def _accept_comma_separated(cls, value: object) -> object:
        """Accept stats=a,b as well as a list."""
        if isinstance(value, str):
            return [stat for stat in value.split(",") if stat]
        return value

    @property
    def include_fully_highly_protected(self) -> bool:
        """The fhp table only covers marine areas."""
        return Stat.FULLY_HIGHLY_PROTECTED in self.stats and self.environment is Environment.MARINE


class LocationArea(BaseModel):
    code: str
    protected_area: float


class LocationStats(BaseModel):
    locations_area: list[LocationArea]
    total_area: float
    total_protected_area: float


class AnalysisResponse(LocationStats):
    """Response body for POST /."""

    fully_highly_protected: LocationStats | None = None
