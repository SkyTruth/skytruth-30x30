import type { Feature } from 'geojson';

export type ClickedPa = {
  wdpaid?: string;
  wdpaPId?: string;
  zoneId?: string;
  // Tile fields, used when an MPAtlas zone has no `/pas` row (not yet established).
  name?: string;
  protectionLevelSlug?: string;
  establishmentStageSlug?: string;
  designation?: string;
  year?: string | number;
  locationCode?: string;
};

// The pipeline writes missing ids as the strings pandas prints for nulls, in
// both the tiles and the database; none of them may ever reach a query.
const MISSING_IDS = new Set(['', 'None', 'nan', 'NaN', '<NA>', 'null']);

export const normalizeId = (value: unknown) =>
  value == null || MISSING_IDS.has(String(value)) ? undefined : String(value);

// The pipeline's conversion of MPAtlas's raw establishment stage to the DB slug.
const ESTABLISHMENT_STAGE_SLUGS: Record<string, string> = {
  'actively managed': 'actively-managed',
  designated: 'designated',
  implemented: 'implemented',
  unknown: 'unknown',
  'proposed/committed': 'proposed-committed',
};

// The WDPA and MPAtlas tilesets spell the same ids differently.
export const readClickedPa = (properties: Feature['properties']): ClickedPa => ({
  wdpaid: normalizeId(properties.WDPAID ?? properties.wdpa_id),
  wdpaPId: normalizeId(properties.WDPA_PID ?? properties.wdpa_pid),
  zoneId: normalizeId(properties.zone_id),
  name: properties.name ?? properties.NAME,
  protectionLevelSlug: properties.protection,
  establishmentStageSlug: ESTABLISHMENT_STAGE_SLUGS[properties.establishm] ?? properties.establishm,
  designation: properties.designatio,
  year: properties.year,
  locationCode: properties.location_i,
});

// Every id a feature carries, so distinct tile features never collapse.
export const clickedPaKey = (pa: ClickedPa) => {
  const key = [pa.wdpaPId, pa.wdpaid, pa.zoneId].join('|');
  return key === '||' ? undefined : key;
};

// The card a feature will land in: parcel, else site, else zone (mirrors the merge).
export const clickedCardKey = (pa: ClickedPa) =>
  pa.wdpaPId ?? pa.wdpaid ?? (pa.zoneId ? `zone-${pa.zoneId}` : undefined);

// MPAtlas's raw `country` field is a delimited list of ISO3 codes; mirror the
// pipeline, which splits it and maps Antarctica to the high seas and Åland to Finland.
export const readTileLocations = (raw: string | undefined) =>
  (raw ?? '')
    .split(/[;:,]/)
    .map((code) => code.trim())
    .filter(Boolean)
    .map((code) => {
      if (code === 'ATA') return { code: 'ABNJ', type: 'highseas' };
      if (code === 'ALA') return { code: 'FIN', type: 'country' };
      return { code, type: 'country' };
    });
