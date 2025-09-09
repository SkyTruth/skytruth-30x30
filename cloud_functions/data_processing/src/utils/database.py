import os

import psycopg
from psycopg.rows import dict_row

from src.utils.logger import Logger

logger = Logger()


def get_connection():
    """Establish a connection to the database"""
    try:
        DATABASE_USERNAME = os.environ.get("DATABASE_USERNAME", None)
        DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD", None)
        DATABASE_NAME = os.environ.get("DATABASE_NAME", None)
        DATABASE_HOST = os.environ.get("DATABASE_HOST", None)

        print("CHECK", DATABASE_NAME, DATABASE_PASSWORD, DATABASE_NAME, DATABASE_HOST)
        if (
            DATABASE_NAME is None
            or DATABASE_PASSWORD is None
            or DATABASE_USERNAME is None
            or DATABASE_HOST is None
        ):
            raise ValueError("Missing DB Crednetials")

        conn = psycopg.connect(
            dbname=DATABASE_NAME,
            user=DATABASE_USERNAME,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=5432,
            row_factory=dict_row,
        )

        return conn

    except Exception as excep:
        logger.error(
            {"message": "Failed to establish connection with database", "error": str(excep)}
        )


def get_pas(verbose: bool = False) -> list[dict]:
    """get all of the PAS and their related values from the DB"""
    conn = get_connection()

    pas_query = """
      WITH child_ids AS (
        SELECT 
          pas.id AS pas_id
          ,array_agg(c.id) FILTER (WHERE c.id IS NOT NULL) AS children
        FROM pas pas
          LEFT JOIN pas_children_links pcl 
          ON pas.id = pcl.pa_id
        LEFT JOIN pas c 
          ON pcl.inv_pa_id = c.id
        GROUP BY pas.id
      )
      ,parent_ids AS (
        SELECT pas.id AS pas_id,
              array_agg(p.id) FILTER (WHERE p.id IS NOT NULL) AS parents
        FROM pas pas
        LEFT JOIN pas_parent_links ppl ON pas.id = ppl.pa_id
        LEFT JOIN pas p ON p.id = ppl.inv_pa_id
        GROUP BY pas.id
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
        ,mes.slug AS establishment_stage
        ,cid.children
        ,pid.parents
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
        ,pid.parents;
    """
    if verbose:
        print("Fetching PAS...")
    with conn.cursor() as curr:
        curr.execute(pas_query)
        rows = curr.fetchall()

    conn.close()
    print("TEST RESPONSE", rows[17])
    return rows
