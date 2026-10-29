import type useLocationName from '@/hooks/use-location-name';
import { pickLocalized } from '@/lib/utils/pick-localized';
import { Pa } from '@/types/generated/strapi.schemas';

import { ClickedPa, normalizeId, readTileLocations } from './parse-tile-click';

/**
 * One protected area, assembled from every `/pas` row sharing its parcel id
 * (or site id when there is no parcel): the Protected Planet row carries the
 * IUCN category, the MPAtlas row carries the MPAA protection level and zone id,
 * and transboundary sites contribute one row per country.
 */
export type MergedPa = {
  id: string;
  wdpaid: string;
  wdpaPId?: string;
  name?: string;
  area?: number;
  designation?: string;
  year?: string | number;
  protectionStatus?: { slug?: string; name?: string };
  mpaaProtectionLevel?: string;
  mpaaEstablishmentStage?: { slug?: string; name?: string };
  iucnCategory?: string;
  locations: string[];
  zoneId?: string;
  isMarine: boolean;
};

export type MergeContext = {
  locale: string;
  getLocationName: ReturnType<typeof useLocationName>;
  isIhoActive: boolean; // TECH-3764: Clean up iho flag
  protectionLevelNames?: Record<string, string>;
  establishmentStageNames?: Record<string, string>;
};

const mergeParcelGroup = (id: string, group: Pa[], context: MergeContext): MergedPa => {
  const { locale, getLocationName, isIhoActive } = context;
  const baseRow = group.find((row) => row.data_source?.slug === 'protected-planet') ?? group[0];

  const iucnCategory = group.find((row) => row.iucn_category)?.iucn_category;
  const mpaaProtectionLevel = group.find((row) => row.mpaa_protection_level)?.mpaa_protection_level;
  const mpaaEstablishmentStage = group.find(
    (row) => row.mpaa_establishment_stage
  )?.mpaa_establishment_stage;
  const protectionStatus = pickLocalized(baseRow.protection_status, locale);
  const establishmentStage = pickLocalized(mpaaEstablishmentStage, locale);

  const locationsByCode = new Map<string, string>();
  group.forEach((row) => {
    if (row.location?.type === 'sea' && !isIhoActive) return;
    const name = getLocationName(row.location);
    if (row.location?.code && name) locationsByCode.set(row.location.code, name);
  });

  return {
    id,
    wdpaid: normalizeId(group[0].wdpaid) ?? '',
    wdpaPId: normalizeId(group[0].wdpa_p_id),
    name: baseRow.name,
    area: baseRow.area,
    protectionStatus: protectionStatus && {
      slug: protectionStatus.slug,
      name: protectionStatus.name,
    },
    mpaaProtectionLevel: pickLocalized(mpaaProtectionLevel, locale)?.name,
    mpaaEstablishmentStage: establishmentStage && {
      slug: establishmentStage.slug,
      name: establishmentStage.name,
    },
    iucnCategory: pickLocalized(iucnCategory, locale)?.name,
    locations: [...locationsByCode.values()],
    zoneId: group.map((row) => normalizeId(row.zone_id)).find(Boolean),
    isMarine: baseRow.environment?.slug === 'marine',
  };
};

// An MPAtlas zone that is not yet established has no `/pas` row, so its card
// comes from the tile alone.
const unestablishedZoneCard = (clicked: ClickedPa, context: MergeContext): MergedPa => {
  const { getLocationName, protectionLevelNames, establishmentStageNames } = context;

  return {
    id: `zone-${clicked.zoneId}`,
    wdpaid: clicked.wdpaid ?? '',
    wdpaPId: clicked.wdpaPId,
    name: clicked.name,
    designation: clicked.designation,
    year: clicked.year,
    mpaaProtectionLevel:
      protectionLevelNames?.[clicked.protectionLevelSlug] ?? clicked.protectionLevelSlug,
    mpaaEstablishmentStage: clicked.establishmentStageSlug
      ? {
          slug: clicked.establishmentStageSlug,
          name:
            establishmentStageNames?.[clicked.establishmentStageSlug] ??
            clicked.establishmentStageSlug,
        }
      : undefined,
    locations: [
      ...new Set(
        readTileLocations(clicked.locationCode).map((location) => getLocationName(location))
      ),
    ].filter(Boolean),
    zoneId: clicked.zoneId,
    isMarine: true,
  };
};

// Sites without a zone id first, by WDPAID; then MPAtlas zones by zone id.
const byZoneThenWdpaid = (a: MergedPa, b: MergedPa) => {
  if (!a.zoneId !== !b.zoneId) return a.zoneId ? 1 : -1;
  if (a.zoneId) return a.zoneId.localeCompare(b.zoneId ?? '', undefined, { numeric: true });
  return (
    a.wdpaid.localeCompare(b.wdpaid, undefined, { numeric: true }) ||
    a.id.localeCompare(b.id, undefined, { numeric: true })
  );
};

export const mergeProtectedAreas = (
  rows: Pa[],
  clicked: ClickedPa[],
  context: MergeContext
): MergedPa[] => {
  // Group by parcel when the row has one, else by site.
  const rowsById = new Map<string, Pa[]>();
  rows.forEach((row) => {
    const id =
      normalizeId(row.wdpa_p_id) ??
      normalizeId(row.wdpaid) ??
      `zone-${normalizeId(row.zone_id) ?? row.id}`;
    rowsById.set(id, [...(rowsById.get(id) ?? []), row]);
  });

  const knownIds = new Set(
    rows.flatMap((row) => [row.zone_id, row.wdpa_p_id, row.wdpaid].map(normalizeId))
  );
  const unestablishedZones = clicked
    .filter(
      (pa) => pa.zoneId && ![pa.zoneId, pa.wdpaPId, pa.wdpaid].some((id) => id && knownIds.has(id))
    )
    .map((pa) => unestablishedZoneCard(pa, context));

  const fromApi = [...rowsById.entries()].map(([id, group]) =>
    mergeParcelGroup(id, group, context)
  );

  return [...fromApi, ...unestablishedZones].sort(byZoneThenWdpaid);
};
