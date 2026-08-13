import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMap } from 'react-map-gl';

import type { Feature } from 'geojson';
import { useAtomValue } from 'jotai';
import { useLocale, useTranslations } from 'next-intl';

import { layersInteractiveIdsAtom, popupAtom } from '@/containers/map/store';
import { cn } from '@/lib/classnames';
import { format } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { useGetLocations } from '@/types/generated/location';
import { useGetPas } from '@/types/generated/pa';
import { LayerTyped } from '@/types/layers';

const TERMS_CLASSES = 'font-mono uppercase';

const ProtectedAreaPopup: FCWithMessages<{ layerSlug: string }> = ({ layerSlug }) => {
  const t = useTranslations('containers.map');

  const locale = useLocale();
  const [rendered, setRendered] = useState(false);
  const DATA_REF = useRef<Feature['properties'][]>([]);
  const { default: map } = useMap();

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

      // Overlapping features at the click point are distinct sites (tiles are
      // dissolved by WDPAID), but keep one entry per WDPAID just in case.
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

  const locationQuery = useGetLocations(
    {
      locale,
      filters: {
        code: 'GLOB',
      },
    },
    {
      query: {
        select: ({ data }) => data[0],
      },
    }
  );

  // Assigned and rendered in the follow-up commits (merge per WDPAID + card/accordion).
  useGetPas(
    {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['name', 'area', 'wdpaid', 'zone_id'],
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
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

  // Temporary: render the first site only, until the per-site card + accordion lands.
  const [FIRST] = DATA;

  const globalCoveragePercentage =
    (FIRST.GIS_AREA / Number(locationQuery.data?.total_marine_area)) * 100;

  const classNameByMPAType = cn({
    'text-green': FIRST?.PA_DEF === 0,
    'text-violet': FIRST?.PA_DEF === 1,
  });

  return (
    <>
      <div className="space-y-2">
        <h3 className="text-xl font-semibold">{FIRST?.NAME}</h3>
        {locationQuery.isFetching && !locationQuery.isFetched && (
          <span className="text-sm">{t('loading')}</span>
        )}
        {locationQuery.isFetched && !locationQuery.data && (
          <span className="text-sm">{t('no-data-available')}</span>
        )}
        {locationQuery.isFetched && locationQuery.data && (
          <>
            <dl className="space-y-2">
              <dt className={TERMS_CLASSES}>{t('global-coverage')}</dt>
              <dd className={`font-mono text-6xl tracking-tighter ${classNameByMPAType}`}>
                {format({
                  locale,
                  value: globalCoveragePercentage,
                  id: 'formatPercentage',
                })}
              </dd>
              <dd className={`font-mono text-xl ${classNameByMPAType}`}>
                {t('area-km2', {
                  area: format({
                    locale,
                    value: FIRST?.GIS_AREA,
                    id: 'formatKM',
                    options: {
                      maximumSignificantDigits: 3,
                    },
                  }),
                })}
              </dd>
            </dl>
          </>
        )}
      </div>
    </>
  );
};

ProtectedAreaPopup.messages = ['containers.map'];

export default ProtectedAreaPopup;
