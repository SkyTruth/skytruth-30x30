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
import { layersInteractiveIdsAtom, popupAtom } from '@/containers/map/store';
import { useFeatureFlag } from '@/hooks/use-feature-flag';
import useLocationName from '@/hooks/use-location-name';
import { cn } from '@/lib/classnames';
import { format } from '@/lib/utils/formats';
import { pickLocalized } from '@/lib/utils/pick-localized';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { useGetPas } from '@/types/generated/pa';
import { Pa } from '@/types/generated/strapi.schemas';
import { LayerTyped } from '@/types/layers';

const TERMS_CLASSES = 'font-mono font-bold uppercase';

/**
 * One protected area, assembled from every `/pas` row sharing its WDPAID: the
 * Protected Planet row carries the IUCN category, the MPAtlas row carries the
 * MPAA protection level and zone id, and transboundary sites contribute one row
 * per country.
 */
type MergedPa = {
  wdpaid: string;
  name?: string;
  area?: number;
  protectionStatus?: { slug?: string; name?: string };
  mpaaProtectionLevel?: string;
  iucnCategory?: string;
  locations: string[];
  zoneId?: string;
  isMarine: boolean;
};

const ProtectedAreaPopup: FCWithMessages<{ layerSlug: string }> = ({ layerSlug }) => {
  const t = useTranslations('containers.map');

  const locale = useLocale();
  const [rendered, setRendered] = useState(false);
  const DATA_REF = useRef<Feature['properties'][]>([]);
  const { default: map } = useMap();

  const [openPa, setOpenPa] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const getLocationName = useLocationName();
  const isIhoActive = useFeatureFlag('is_iho_active');

  const popup = useAtomValue(popupAtom);
  const layersInteractiveIds = useAtomValue(layersInteractiveIdsAtom);

  const layerQuery = useGetLayers<{
    source: LayerTyped['config']['source'];
    click: LayerTyped['interaction_config']['events'][0];
  }>(
    {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      locale,
      filters: {
        slug: {
          $eq: layerSlug,
        },
      },
      populate: 'metadata',
    },
    {
      query: {
        select: ({ data }) => ({
          source: (data[0] as LayerTyped).config?.source,
          click: (data[0] as LayerTyped)?.interaction_config?.events.find(
            (event) => event.type === 'click'
          ),
        }),
      },
    }
  );

  const DATA = useMemo(() => {
    const source = layerQuery?.data?.source;

    if (source?.type === 'vector' && rendered && popup && map) {
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

      // Overlapping features at the click point are distinct sites, except that
      // one site split across tile boundaries repeats its WDPAID.
      const seen = new Set<unknown>();
      const features = query
        .filter((feature) => feature.source === source.id)
        .map((feature) => feature.properties)
        .filter((properties) => {
          if (properties?.WDPAID == null || seen.has(properties.WDPAID)) return false;
          seen.add(properties.WDPAID);
          return true;
        });

      if (features.length) {
        DATA_REF.current = features;
      }
    }

    return DATA_REF.current;
  }, [popup, layerQuery, layersInteractiveIds, map, rendered]);

  const wdpaids = useMemo(() => DATA.map((properties) => String(properties.WDPAID)), [DATA]);

  const paQuery = useGetPas<Pa[]>(
    {
      // @ts-ignore
      fields: ['name', 'area', 'wdpaid', 'zone_id'],
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
        iucn_category: {
          fields: ['slug', 'name', 'locale'],
          populate: { localizations: { fields: ['slug', 'name', 'locale'] } },
        },
        data_source: { fields: ['slug'] },
        environment: { fields: ['slug'] },
        location: { fields: ['code', 'type'] },
      },
      filters: {
        wdpaid: { $in: wdpaids },
      },
      'pagination[pageSize]': 100,
    },
    {
      query: {
        enabled: wdpaids.length > 0,
        select: ({ data }) => data,
      },
    }
  );

  const mergedPas = useMemo<MergedPa[]>(() => {
    const rows = paQuery.data;
    if (!rows?.length) return [];

    const rowsByWdpaid = new Map<string, Pa[]>();
    rows.forEach((row) => {
      const wdpaid = String(row.wdpaid);
      rowsByWdpaid.set(wdpaid, [...(rowsByWdpaid.get(wdpaid) ?? []), row]);
    });

    // Iterating the clicked ids keeps the popup in click order, which the
    // Strapi `$in` filter does not preserve.
    return wdpaids
      .filter((wdpaid) => rowsByWdpaid.has(wdpaid))
      .map((wdpaid) => {
        const group = rowsByWdpaid.get(wdpaid);
        const baseRow =
          group.find((row) => row.data_source?.slug === 'protected-planet') ?? group[0];

        const iucnCategory = group.find((row) => row.iucn_category)?.iucn_category;
        const mpaaProtectionLevel = group.find(
          (row) => row.mpaa_protection_level
        )?.mpaa_protection_level;
        const protectionStatus = pickLocalized(baseRow.protection_status, locale);

        const locationsByCode = new Map<string, string>();
        group.forEach((row) => {
          if (row.location?.type === 'sea' && !isIhoActive) return;
          const name = getLocationName(row.location);
          if (row.location?.code && name) locationsByCode.set(row.location.code, name);
        });

        return {
          wdpaid,
          name: baseRow.name,
          area: baseRow.area,
          protectionStatus: protectionStatus && {
            slug: protectionStatus.slug,
            name: protectionStatus.name,
          },
          mpaaProtectionLevel: pickLocalized(mpaaProtectionLevel, locale)?.name,
          iucnCategory: pickLocalized(iucnCategory, locale)?.name,
          locations: [...locationsByCode.values()],
          zoneId: group.find((row) => row.zone_id)?.zone_id,
          isMarine: baseRow.environment?.slug === 'marine',
        };
      });
  }, [paQuery.data, wdpaids, locale, getLocationName, isIhoActive]);

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
          <div>
            <dt className={TERMS_CLASSES}>{t('protection-level')}</dt>
            <dd>{pa.mpaaProtectionLevel ?? t('not-assessed')}</dd>
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
      {pa.wdpaid && (
        <a
          href={`https://www.protectedplanet.net/${pa.wdpaid}`}
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
              value={pa.wdpaid}
              key={pa.wdpaid}
              ref={(element) => {
                itemRefs.current[pa.wdpaid] = element;
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
