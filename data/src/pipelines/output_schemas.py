from typing import Union, List
import pandera as pa
from pandera.typing import Index, Series
from pandera.typing.geopandas import GeoDataFrame, GeoSeries
import pandas as pd


class LocationSchema(pa.DataFrameModel):
    id: Index[int] = pa.Field(gt=0, coerce=True)
    code: Series[str] = pa.Field(coerce=True)
    name: Series[str] = pa.Field(coerce=True)
    totalMarineArea: Series[float] = pa.Field(ge=0, coerce=True)  # noqa: N815
    type: Series[str] = pa.Field(
        unique_values_eq=["country", "worldwide", "region", "highseas"], coerce=True
    )
    groups: Series[List[int]] = pa.Field(coerce=True)
    bounds: Series[List[float]] = pa.Field(coerce=True)


class ProtectedAreaExtentSchema(pa.DataFrameModel):
    id: Index[int] = pa.Field(gt=0, coerce=True)
    location: Series[int] = pa.Field(gt=0, coerce=True)
    protection_status: Series[int] = pa.Field(gt=0, coerce=True)
    cumSumProtectedArea: Series[float] = pa.Field(ge=0, coerce=True)  # noqa: N815
    protectedArea: Series[float] = pa.Field(ge=0, coerce=True)  # noqa: N815
    protectedAreasCount: Series[int] = pa.Field(ge=0, coerce=True)  # noqa: N815
    year: Series[int] = pa.Field(ge=2000, coerce=True)


class ProtectionLevelSchema(pa.DataFrameModel):
    id: Index[int] = pa.Field(gt=0, coerce=True)
    location: Series[int] = pa.Field(gt=0, coerce=True)
    mpaa_protection_level: Series[int] = pa.Field(ge=0, coerce=True)
    year: Series[int] = pa.Field(gt=1900, coerce=True)
    area: Series[float] = pa.Field(ge=0, coerce=True)


class FPLSchema(pa.DataFrameModel):
    id: Index[int] = pa.Field(gt=0, coerce=True)
    location: Series[int] = pa.Field(gt=0, coerce=True)
    fishing_protection_level: Series[int] = pa.Field(ge=0, coerce=True)
    area: Series[float] = pa.Field(ge=0, coerce=True)
    pct: Series[float] = pa.Field(ge=0, coerce=True)


class HabitatsSchema(pa.DataFrameModel):
    id: Index[int] = pa.Field(gt=0, coerce=True)
    location: Series[int] = pa.Field(gt=0, coerce=True)
    habitat: Series[int] = pa.Field(gt=0, coerce=True)
    protectedArea: Series[float] = pa.Field(ge=0, coerce=True)  # noqa: N815
    totalArea: Series[float] = pa.Field(ge=0, coerce=True)  # noqa: N815
    year: Series[int] = pa.Field(gt=1800, coerce=True)


class MPAsSchema(pa.DataFrameModel):
    id: Index[int] = pa.Field(gt=0, coerce=True)
    wdpaid: Series[pd.Int64Dtype] = pa.Field(coerce=True, nullable=True)
    child_id: Series[str] = pa.Field(coerce=True)
    name: Series[str] = pa.Field(coerce=True)
    year: Series[pd.Int32Dtype] = pa.Field(gt=1800, nullable=True)
    area: Series[float] = pa.Field(ge=0, coerce=True)
    bbox: Series[List[float]] = pa.Field(coerce=True)
    location: Series[int] = pa.Field(ge=0, coerce=True)
    protection_status: Series[int] = pa.Field(ge=0, nullable=True)
    mpaa_establishment_stage: Series[pd.Int32Dtype] = pa.Field(ge=0, nullable=True, coerce=True)
    mpaa_protection_level: Series[pd.Int32Dtype] = pa.Field(ge=0, nullable=True, coerce=True)
    mpa_iucn_category: Series[pd.Int32Dtype] = pa.Field(coerce=True, nullable=True)
    designation: Series[str] = pa.Field(coerce=True, nullable=True)
    is_child: Series[bool] = pa.Field(coerce=True)
    children: Series[List[int]] = pa.Field(coerce=True, nullable=True)
    data_source: Series[int] = pa.Field(coerce=True)


class MPAsTableOTFSchema(pa.DataFrameModel):
    MRGID: Index[pd.Int64Dtype] = pa.Field(coerce=True)
    GEONAME: Series[str] = pa.Field(coerce=True)
    POL_TYPE: Series[str] = pa.Field(coerce=True)
    AREA_KM2: Series[float] = pa.Field(ge=0, coerce=True)
    ISO_SOV1: Series[str] = pa.Field(coerce=True)
    ISO_SOV2: Series[str] = pa.Field(coerce=True, nullable=True)
    ISO_SOV3: Series[str] = pa.Field(coerce=True, nullable=True)
    geometry: GeoSeries

    # TODO: Check if it is a valid geometry column
    # @pa.check("geometry")
    # def is_valid_geometry(cls, series):
    #     return series.map(lambda x: isinstance(x, Point))
