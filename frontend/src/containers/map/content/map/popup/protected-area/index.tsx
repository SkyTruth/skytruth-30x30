import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMap } from 'react-map-gl';

import type { Feature } from 'geojson';
import { useAtomValue } from 'jotai';
import { ChevronDown } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import {
  Accordion,
  AccordionContent,
  AccordionHeader,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { layersInteractiveAtom, layersInteractiveIdsAtom, popupAtom } from '@/containers/map/store';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import useLocationName from '@/hooks/use-location-name';
import { cn } from '@/lib/classnames';
import { format } from '@/lib/utils/formats';
import { pickLocalized } from '@/lib/utils/pick-localized';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { useGetMpaaEstablishmentStages } from '@/types/generated/mpaa-establishment-stage';
import { useGetMpaaProtectionLevels } from '@/types/generated/mpaa-protection-level';
import { useGetPas } from '@/types/generated/pa';
import { Pa } from '@/types/generated/strapi.schemas';
import { LayerTyped } from '@/types/layers';

const TERMS_CLASSES = 'font-mono font-bold uppercase';

/**
 * One protected area, assembled from every `/pas` row sharing its parcel id
 * (or site id when there is no parcel): the Protected Planet row carries the
 * IUCN category, the MPAtlas row carries the MPAA protection level and zone id,
 * and transboundary sites contribute one row per country.
 */
type MergedPa = {
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

type ClickedPa = {
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

const normalizeId = (value: unknown) => (value == null || value === '' ? undefined : String(value));

// The WDPA and MPAtlas tilesets spell the same ids differently.
const readClickedPa = (properties: Feature['properties']): ClickedPa => ({
  wdpaid: normalizeId(properties.WDPAID ?? properties.wdpa_id),
  wdpaPId: normalizeId(properties.WDPA_PID ?? properties.wdpa_pid),
  zoneId: normalizeId(properties.zone_id),
  name: properties.name ?? properties.NAME,
  protectionLevelSlug: properties.protection,
  establishmentStageSlug: properties.establishm,
  designation: properties.designatio,
  year: properties.year,
  locationCode: properties.location_i,
});

// MPAtlas's raw `country` field is a delimited list of ISO3 codes; mirror the
// pipeline, which splits it and maps Antarctica to the high seas and Åland to Finland.
const readTileLocations = (raw: string | undefined) =>
  (raw ?? '')
    .split(/[;:,]/)
    .map((code) => code.trim())
    .filter(Boolean)
    .map((code) => {
      if (code === 'ATA') return { code: 'ABNJ', type: 'highseas' };
      if (code === 'ALA') return { code: 'FIN', type: 'country' };
      return { code, type: 'country' };
    });

// `layerSlug` comes from the CMS config; the popup reads every protected-area layer instead.
const ProtectedAreaPopup: FCWithMessages<{ layerSlug: string }> = () => {
  const t = useTranslations('containers.map');

  const locale = useLocale();
  const [rendered, setRendered] = useState(false);
  const DATA_REF = useRef<ClickedPa[]>([]);
  const { default: map } = useMap();

  const [openPa, setOpenPa] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const getLocationName = useLocationName();
  const isIhoActive = useFeatureFlag('is_iho_active');

  const { data: protectionLevelNames } = useGetMpaaProtectionLevels<Record<string, string>>(
    {
      locale,
      // @ts-ignore
      fields: ['name', 'slug'],
    },
    {
      query: {
        select: ({ data }) => Object.fromEntries(data.map((level) => [level.slug, level.name])),
        placeholderData: { data: [] },
      },
    }
  );

  const { data: establishmentStageNames } = useGetMpaaEstablishmentStages<Record<string, string>>(
    {
      locale,
      // @ts-ignore
      fields: ['name', 'slug'],
    },
    {
      query: {
        select: ({ data }) => Object.fromEntries(data.map((stage) => [stage.slug, stage.name])),
        placeholderData: { data: [] },
      },
    }
  );

  const popup = useAtomValue(popupAtom);
  const layersInteractive = useAtomValue(layersInteractiveAtom);
  const layersInteractiveIds = useAtomValue(layersInteractiveIdsAtom);

  const sourcesQuery = useGetLayers<string[]>(
    {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      locale,
      filters: {
        slug: {
          $in: layersInteractive,
        },
      },
    },
    {
      query: {
        enabled: layersInteractive.length > 0,
        select: ({ data }) =>
          (data as LayerTyped[])
            .filter(
              (layer) =>
                layer.interaction_config?.['@@type'] === 'ProtectedAreaPopup' &&
                layer.config?.source?.type === 'vector'
            )
            .map((layer) => layer.config.source.id),
      },
    }
  );

  const DATA = useMemo(() => {
    const sources = sourcesQuery.data;

    if (sources?.length && rendered && popup && map) {
      const point = map.project(popup.lngLat);

      // check if the point is outside the canvas
      if (
        point.x < 0 ||
        point.x > map.getCanvas().width ||
        point.y < 0 ||
        point.y > map.getCanvas().height
      ) {
        return DATA_REF.current;
      }
      const query = map.queryRenderedFeatures(point, {
        layers: layersInteractiveIds,
      });

      // The same parcel can appear under several layers and across tile boundaries.
      const seen = new Set<string>();
      const features = query
        .filter((feature) => sources.includes(feature.source))
        .map((feature) => readClickedPa(feature.properties))
        .filter((clicked) => {
          const key = [clicked.wdpaPId, clicked.wdpaid, clicked.zoneId].join('|');
          if (key === '||' || seen.has(key)) return false;
          seen.add(key);
          return true;
        });

      if (features.length) {
        DATA_REF.current = features;
      }
    }

    return DATA_REF.current;
  }, [popup, sourcesQuery.data, layersInteractiveIds, map, rendered]);

  const filters = useMemo(() => {
    const parcelIds = DATA.map((clicked) => clicked.wdpaPId).filter(Boolean);
    const siteIds = DATA.filter((clicked) => !clicked.wdpaPId)
      .map((clicked) => clicked.wdpaid)
      .filter(Boolean);
    const zoneIds = DATA.map((clicked) => clicked.zoneId).filter(Boolean);

    return {
      $or: [
        parcelIds.length > 0 && { wdpa_p_id: { $in: parcelIds } },
        siteIds.length > 0 && { wdpaid: { $in: siteIds } },
        zoneIds.length > 0 && { zone_id: { $in: zoneIds } },
      ].filter(Boolean),
    };
  }, [DATA]);

  const paQuery = useGetPas<Pa[]>(
    {
      // @ts-ignore
      fields: ['name', 'area', 'wdpaid', 'wdpa_p_id', 'zone_id'],
      // @ts-ignore
      populate: {
        protection_status: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        mpaa_protection_level: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        mpaa_establishment_stage: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        iucn_category: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        data_source: { fields: ['slug'] },
        environment: { fields: ['slug'] },
        location: { fields: ['code', 'type'] },
      },
      filters,
      'pagination[pageSize]': 100,
    },
    {
      query: {
        enabled: DATA.length > 0,
        select: ({ data }) => data,
      },
    }
  );

  const mergedPas = useMemo<MergedPa[]>(() => {
    const rows = paQuery.data ?? [];

    // Group by parcel when the row has one, else by site.
    const rowsById = new Map<string, Pa[]>();
    rows.forEach((row) => {
      const id = row.wdpa_p_id || String(row.wdpaid);
      rowsById.set(id, [...(rowsById.get(id) ?? []), row]);
    });

    const knownIds = new Set(rows.flatMap((row) => [row.zone_id, row.wdpa_p_id, row.wdpaid]));

    // An MPAtlas zone that is not yet established has no `/pas` row, so its
    // card comes from the tile alone.
    const unestablishedZones: MergedPa[] = DATA.filter(
      (clicked) =>
        clicked.zoneId &&
        ![clicked.zoneId, clicked.wdpaPId, clicked.wdpaid].some((id) => id && knownIds.has(id))
    ).map((clicked) => ({
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
    }));

    const fromApi: MergedPa[] = [...rowsById.entries()].map(([id, group]) => {
      const wdpaid = String(group[0].wdpaid);
      const baseRow = group.find((row) => row.data_source?.slug === 'protected-planet') ?? group[0];

      const iucnCategory = group.find((row) => row.iucn_category)?.iucn_category;
      const mpaaProtectionLevel = group.find(
        (row) => row.mpaa_protection_level
      )?.mpaa_protection_level;
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
        wdpaid,
        wdpaPId: group[0].wdpa_p_id,
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
        zoneId: group.find((row) => row.zone_id)?.zone_id,
        isMarine: baseRow.environment?.slug === 'marine',
      };
    });

    // Sites without a zone id first, by WDPAID; then MPAtlas zones by zone id.
    return [...fromApi, ...unestablishedZones].sort((a, b) => {
      if (!a.zoneId !== !b.zoneId) return a.zoneId ? 1 : -1;
      if (a.zoneId) return Number(a.zoneId) - Number(b.zoneId);
      return (
        a.wdpaid.localeCompare(b.wdpaid, undefined, { numeric: true }) ||
        a.id.localeCompare(b.id, undefined, { numeric: true })
      );
    });
  }, [
    paQuery.data,
    DATA,
    locale,
    getLocationName,
    isIhoActive,
    protectionLevelNames,
    establishmentStageNames,
  ]);

  // Anchoring on the trigger rather than the content keeps this independent of
  // the expand animation.
  useEffect(() => {
    const container = scrollRef.current;
    const item = itemRefs.current[openPa];
    if (!container || !item) return;

    container.scrollTop += item.getBoundingClientRect().top - container.getBoundingClientRect().top;
  }, [openPa]);

  // handle renderer
  const handleMapRender = useCallback(() => {
    setRendered(map?.loaded() && map?.areTilesLoaded());
  }, [map]);

  useEffect(() => {
    map?.on('render', handleMapRender);

    setRendered(map?.loaded() && map?.areTilesLoaded());

    return () => {
      map?.off('render', handleMapRender);
    };
  }, [map, handleMapRender]);

  if (!DATA.length) return null;

  const renderPa = (pa: MergedPa, showName: boolean) => (
    <div className="space-y-2">
      {showName && <h3 className="text-xl font-semibold">{pa.name}</h3>}
      <dl className="space-y-2">
        {pa.area != null && (
          <div>
            <dt className={TERMS_CLASSES}>{t('area')}</dt>
            <dd>
              {t('area-km2', {
                area: format({
                  locale,
                  value: pa.area,
                  id: 'formatKM',
                  options: {
                    maximumSignificantDigits: 3,
                  },
                }),
              })}
            </dd>
          </div>
        )}
        {pa.protectionStatus?.name && (
          <div>
            <dt className={TERMS_CLASSES}>{t('type')}</dt>
            <dd
              className={cn('font-semibold', {
                'text-violet': pa.protectionStatus.slug === 'pa',
                'text-green': pa.protectionStatus.slug === 'oecm',
              })}
            >
              {pa.protectionStatus.name}
            </dd>
          </div>
        )}
        {pa.isMarine && (
          <>
            <div>
              <dt className={TERMS_CLASSES}>{t('protection-level')}</dt>
              <dd>{pa.mpaaProtectionLevel ?? t('not-assessed')}</dd>
            </div>
            <div>
              <dt className={TERMS_CLASSES}>{t('establishment-stage')}</dt>
              <dd>{pa.mpaaEstablishmentStage?.name ?? t('n-a')}</dd>
            </div>
          </>
        )}
        {pa.designation && (
          <div>
            <dt className={TERMS_CLASSES}>{t('designation')}</dt>
            <dd>{pa.designation}</dd>
          </div>
        )}
        {pa.year != null && (
          <div>
            <dt className={TERMS_CLASSES}>{t('year')}</dt>
            <dd>{pa.year}</dd>
          </div>
        )}
        <div>
          <dt className={TERMS_CLASSES}>{t('iucn-category')}</dt>
          <dd>{pa.iucnCategory ?? t('n-a')}</dd>
        </div>
        {pa.locations.length > 0 && (
          <div>
            <dt className={TERMS_CLASSES}>{t('location')}</dt>
            <dd>{pa.locations.join(', ')}</dd>
          </div>
        )}
      </dl>
      {pa.mpaaEstablishmentStage?.slug === 'proposed' && (
        <p className="text-xs italic">{t('mpa-not-implemented')}</p>
      )}
      {pa.wdpaid && (
        <a
          href={`https://www.protectedplanet.net/${pa.wdpaid}${
            pa.wdpaPId ? `?site_pid=${pa.wdpaPId}` : ''
          }`}
          target="_blank"
          rel="noopener noreferrer"
          className="block font-semibold underline"
        >
          {t('view-on-protected-planet')}
        </a>
      )}
      {pa.zoneId && (
        <a
          href={`https://mpatlas.org/zones/${pa.zoneId}/`}
          target="_blank"
          rel="noopener noreferrer"
          className="block font-semibold underline"
        >
          {t('view-on-mpatlas')}
        </a>
      )}
      {/* Debug only; remove before merging. */}
      <div className="font-mono text-xs text-gray-300">
        WDPAID {pa.wdpaid} · WDPA_PID {pa.wdpaPId ?? '-'} · ZONE_ID {pa.zoneId ?? '-'}
      </div>
    </div>
  );

  return (
    <div
      ref={scrollRef}
      className={cn(
        DATA.length > 1 ? 'max-h-[30vh] overflow-y-auto overflow-x-hidden' : 'flex flex-col gap-2'
      )}
    >
      {paQuery.isFetching && (
        <div className="my-4 text-center font-mono text-xl">{t('loading')}</div>
      )}
      {!paQuery.isFetching && !mergedPas.length && (
        <div className="my-4 text-center font-mono">{t('no-data-available')}</div>
      )}
      {!paQuery.isFetching && mergedPas.length === 1 && renderPa(mergedPas[0], true)}
      {!paQuery.isFetching && mergedPas.length > 1 && (
        <Accordion
          type="single"
          collapsible
          className="divide-y"
          value={openPa}
          onValueChange={setOpenPa}
        >
          {mergedPas.map((pa) => (
            <AccordionItem
              value={pa.id}
              key={pa.id}
              ref={(element) => {
                itemRefs.current[pa.id] = element;
              }}
            >
              <AccordionHeader>
                <AccordionTrigger className="group grid w-full grid-cols-6 justify-items-start gap-4 py-2 text-left">
                  <span className="col-span-5 col-start-1 font-semibold">{pa.name}</span>
                  <ChevronDown
                    aria-hidden
                    className="ease-&lsqb;cubic-bezier(0.87,_0,_0.13,_1)&rsqb; transition-transform duration-300 group-data-[state=open]:rotate-180"
                  />
                </AccordionTrigger>
              </AccordionHeader>
              <AccordionContent className="pb-1 text-xs">{renderPa(pa, false)}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      )}
    </div>
  );
};

ProtectedAreaPopup.messages = [
  'containers.map',
  // Required by the `useLocationName` hook
  'locations',
];

export default ProtectedAreaPopup;
