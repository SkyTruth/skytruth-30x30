import os

import psycopg
from psycopg.rows import dict_row
from shapely.geometry import MultiPolygon, Polygon
from sqlalchemy import create_engine, text

from src.core.params import BUCKET
from src.utils.gcp import load_zipped_shapefile_from_gcs
from src.utils.logger import Logger

logger = Logger()


def get_connection(format: str = "psycopg"):
    """
    Establish a connection to the database

    Parameter
    ----------
    format : str
      Method used to connect to database ('psycopg' or 'sqlalchemy')
    """
    try:
        DATABASE_USERNAME = os.environ.get("DATABASE_USERNAME", None)
        DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD", None)
        DATABASE_NAME = os.environ.get("DATABASE_NAME", None)
        DATABASE_HOST = os.environ.get("DATABASE_HOST", None)

        if (
            DATABASE_NAME is None
            or DATABASE_PASSWORD is None
            or DATABASE_USERNAME is None
            or DATABASE_HOST is None
        ):
            raise ValueError("Missing DB Crednetials")

        if format == "psycopg":
            return psycopg.connect(
                dbname=DATABASE_NAME,
                user=DATABASE_USERNAME,
                password=DATABASE_PASSWORD,
                host=DATABASE_HOST,
                port=5432,
                row_factory=dict_row,
            )

        elif format == "sqlalchemy":
            return create_engine(
                f"postgresql+psycopg://{DATABASE_USERNAME}:{DATABASE_PASSWORD}@{DATABASE_HOST}:5432/{DATABASE_NAME}"
            )

    except Exception as excep:
        logger.error(
            {"message": "Failed to establish connection with database", "error": str(excep)}
        )


def update_cb(table_name, gcs_file, verbose: bool = False):
    """
    Update Conservation Builder table from GCS file.

    Parameters
    ----------
    table_name : str
      Name of the table to update.
    gcs_file : str
      GCS path of the file.
    verbose : bool
      Whether to print progress messages.
    """
    try:
        conn = get_connection(format="sqlalchemy")

        if verbose:
            logger.info({"message": f"Loading {gcs_file}..."})
        gdf = load_zipped_shapefile_from_gcs(filename=gcs_file, bucket=BUCKET)

        # Filter columns
        gdf = gdf[["location", "geometry"]]

        # Turn Polygon to MultiPolygon for consistency
        gdf["geometry"] = gdf["geometry"].apply(
            lambda geom: MultiPolygon([geom]) if isinstance(geom, Polygon) else geom
        )

        # Update geometry name for consistency in PostgreSQL database
        gdf = gdf.rename_geometry("the_geom")

        # Write to PostgreSQL database
        with conn.connect() as connection:
            if table_name == "gadm_minus_pa_v2":
                # Write temp table to PostgreSQL
                if verbose:
                    logger.info({"message": "Uploading data to PostgreSQL..."})
                gdf.to_postgis(
                    name=f"{table_name}_temp",
                    schema="data",
                    con=conn,
                    if_exists="replace",
                    dtype={"the_geom": "Geometry(MultiPolygon, 4326)"},
                )
                # Subdivide geometries and create spatial index for faster querying
                if verbose:
                    logger.info({"message": "Subdividing geometries and creating spatial index..."})
                sql_command = f"""
                    DROP TABLE IF EXISTS data.{table_name};

                    -- Subdivide into final table (max 400 vertices per row)
                    CREATE TABLE data.{table_name} AS
                        SELECT
                            location,
                            ST_Multi(ST_Subdivide(ST_MakeValid(the_geom), 400)) AS the_geom
                        FROM data.{table_name}_temp;

                    -- Add primary key
                    ALTER TABLE data.{table_name} ADD COLUMN id SERIAL PRIMARY KEY;

                    -- Create GIST index for fast spatial querying
                    CREATE INDEX gist_{table_name}_geom
                        ON data.{table_name}
                        USING GIST (the_geom);

                    DROP TABLE data.{table_name}_temp;
                    ANALYZE data.{table_name};
                    """

            elif table_name == "eez_minus_mpa_v2":
                # Write to PostgreSQL
                if verbose:
                    logger.info({"message": "Uploading data to PostgreSQL..."})
                gdf.to_postgis(
                    name=table_name,
                    schema="data",
                    con=conn,
                    if_exists="replace",
                    dtype={"the_geom": "Geometry(MultiPolygon, 4326)"},
                )
                # Create spatial index for faster querying
                sql_command = f"""
                    -- Add primary key
                    ALTER TABLE data.{table_name} ADD COLUMN id SERIAL PRIMARY KEY;

                    -- Create GIST index for fast spatial querying
                    CREATE INDEX gist_{table_name}_geom
                        ON data.{table_name}
                        USING GIST (the_geom);

                    ANALYZE data.{table_name};
                    """

            connection.execute(text(sql_command))
            connection.commit()

    except Exception as excep:
        logger.error({"message": "Failed to update table", "error": str(excep)})


def get_pas(verbose: bool = False) -> list[dict]:
    """get all of the PAS and their related values from the DB"""
    try:
        conn = get_connection()

        pas_query = """
      WITH child_ids AS (
        SELECT 
          pas.id AS pas_id
          ,jsonb_agg(
            jsonb_build_object('id', c.id)
          ) FILTER (WHERE c.id IS NOT NULL) AS children
        FROM pas pas
          LEFT JOIN pas_children_links pcl 
          ON pas.id = pcl.pa_id
        LEFT JOIN pas c 
          ON pcl.inv_pa_id = c.id
        GROUP BY pas.id
      )
      ,parent_ids AS (
        SELECT 
          pas.id AS pas_id
          ,CASE 
            WHEN p.id IS NULL THEN NULL
            ELSE jsonb_build_object(
              'id', p.id
            )
        END AS parent
        FROM pas pas
          LEFT JOIN pas_parent_links ppl 
            ON pas.id = ppl.pa_id
        LEFT JOIN pas p 
          ON p.id = ppl.inv_pa_id
      )
      SELECT 
        pas.id
        ,pas."name" 
        ,pas.area
        ,pas."year"
        ,pas.bbox
        ,pas.coverage
        ,pas.wdpaid
        ,pas.wdpa_p_id
        ,pas.zone_id
        ,pas.designation
        ,ps.slug AS protection_status
        ,e.slug AS environment
        ,l.code AS location
        ,ds.slug AS data_source
        ,mpl.slug AS mpaa_protection_level
        ,mic.slug AS iucn_category
        ,mes.slug AS mpaa_establishment_stage
        ,cid.children
        ,pid.parent
      FROM pas pas
      -- Children --
        LEFT JOIN child_ids AS cid
          ON cid.pas_id = pas.id
      -- Parents --
        LEFT JOIN parent_ids AS pid
          ON pid.pas_id = pas.id
      -- protection status --
        LEFT JOIN pas_protection_status_links ppsl 
          ON pas.id = ppsl.pa_id
        LEFT JOIN protection_statuses ps
          ON ppsl.protection_status_id = ps.id
      -- Environment
        LEFT JOIN pas_environment_links pel 
          ON pas.id = pel.pa_id
        LEFT JOIN environments e
          ON pel.environment_id = e.id
      -- Location --
        LEFT JOIN pas_location_links pll  
          ON pas.id = pll.pa_id
        LEFT JOIN locations l
          ON pll.location_id  = l.id
      -- Data Source --
        LEFT JOIN pas_data_source_links pdsl  
          ON pas.id = pdsl.pa_id
        LEFT JOIN data_sources ds
          ON pdsl.data_source_id = ds.id
      -- Protection Level --
        LEFT JOIN pas_mpaa_protection_level_links pmpll 
          ON pas.id = pmpll.pa_id
        LEFT JOIN mpaa_protection_levels mpl 
          ON pmpll.mpaa_protection_level_id = mpl.id
      -- IUCN Category --
        LEFT JOIN pas_iucn_category_links picl 
          ON pas.id = picl.pa_id
        LEFT JOIN mpa_iucn_categories mic 
          ON picl.mpa_iucn_category_id  = mic.id
      -- Establishment Stage --
        LEFT JOIN pas_mpaa_establishment_stage_links pmesl 
          ON pas.id = pmesl.pa_id
        LEFT JOIN mpaa_establishment_stages mes 
          ON pmesl.mpaa_establishment_stage_id  = mes.id
      GROUP BY 
        pas.id
        ,ps.slug
        ,e.slug
        ,l.code
        ,ds.slug
        ,mpl.slug
        ,mic.slug
        ,mes.slug
        ,cid.children
        ,pid.parent;
    """
        if verbose:
            print("Fetching PAs...")
        with conn.cursor() as curr:
            curr.execute(pas_query)
            rows = curr.fetchall()

        conn.close()
        return rows
    except Exception as excep:
        logger.error({"message": "Failed to read PAs from the Database", "error": str(excep)})
