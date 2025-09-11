import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMap } from 'react-map-gl';

import { useRouter } from 'next/router';

import type { Feature } from 'geojson';
import { useAtom, useAtomValue } from 'jotai';
import { ChevronDown } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import {
  Accordion,
  AccordionItem,
  AccordionContent,
  AccordionTrigger,
  AccordionHeader,
} from '@/components/ui/accordion';
import { PAGES } from '@/constants/pages';
import { useMapSearchParams, useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { layersInteractiveIdsAtom, popupAtom } from '@/containers/map/store';
import { formatPercentage, formatKM } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';
import { ProtectionCoverageStatListResponseDataItem } from '@/types/generated/strapi.schemas';
import { LayerTyped } from '@/types/layers';

import { POPUP_PROPERTIES_BY_SOURCE } from '../constants';

import StatCard from './StatCard';

const BoundariesPopup: FCWithMessages<{ layerSlug: string }> = ({ layerSlug }) => {
  const t = useTranslations('containers.map');
  const locale = useLocale();

  const [rendered, setRendered] = useState(false);

  const geometryDataRef = useRef<Feature['properties'] | undefined>();
  const { default: map } = useMap();

  const searchParams = useMapSearchParams();
  const [activeLayers] = useSyncMapLayers();

  const { push } = useRouter();

  const [popup, setPopup] = useAtom(popupAtom);
  const layersInteractiveIds = useAtomValue(layersInteractiveIdsAtom);

  const { data, isFetching: isPending } = useGetLayers<{
    source: LayerTyped['config']['source'];
    environment: string;
  }>(
    {
      locale,
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['config', 'slug'],
      // TODO TECH 3174: Clean up slug, only needed to filter correct layers
      filters: {
        slug: {
          $eq: layerSlug,
        },
      },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        environment: {
          fields: ['slug'],
        },
      },
    },
    {
      query: {
        select: ({ data }) => ({
          source: (data[0].attributes as LayerTyped)?.config?.source,
          environment: data[0].attributes?.environment?.data?.attributes.slug,
        }),
      },
    }
  );

  let source = undefined;
  let environment = undefined;
  if (!isPending) {
    source = data?.source;
    environment = data?.environment;
  }

  const geometryData = useMemo(() => {
    if (source?.type === 'vector' && rendered && popup && map) {
      const point = map.project(popup.lngLat);

      // check if the point is outside the canvas
      if (
        point.x < 0 ||
        point.x > map.getCanvas().width ||
        point.y < 0 ||
        point.y > map.getCanvas().height
      ) {
        return geometryDataRef.current;
      }
      const query = map.queryRenderedFeatures(point, {
        layers: layersInteractiveIds,
      });

      const d = query.find((d) => {
        return d.source === source.id;
      })?.properties;

      geometryDataRef.current = d;

      if (d) {
        return geometryDataRef.current;
      }
    }

    return geometryDataRef.current;
  }, [popup, source, layersInteractiveIds, map, rendered]);

  // const locationCode = useMemo(
  //   () => geometryData?.[POPUP_PROPERTIES_BY_SOURCE[source?.['id']]?.id],
  //   [geometryData, source]
  // );

  const locationCodes = useMemo(() => {
    const locKeys = POPUP_PROPERTIES_BY_SOURCE[source?.['id']]?.ids ?? [];
    const codes = [];
    console.log('LOCKET', source, locKeys, 'geom', geometryData);
    locKeys.forEach((key: string) => geometryData?.[key] && codes.push(geometryData[key]));

    return codes;
  }, [geometryData, source]);

  const localizedLocationName = useMemo(
    () => geometryData?.[POPUP_PROPERTIES_BY_SOURCE[source?.['id']]?.name[locale]],
    [geometryData, locale, source]
  );

  const nameField = useMemo(() => {
    let res = 'name';
    if (locale === 'es') {
      res = 'name_es';
    }
    if (locale === 'fr') {
      res = 'name_fr';
    }
    return res;
  }, [locale]);

  const { data: protectionCoverageStats, isFetching } = useGetProtectionCoverageStats<
    ProtectionCoverageStatListResponseDataItem[]
  >(
    {
      locale,
      filters: {
        location: {
          code: {
            $in: locationCodes,
          },
        },
        is_last_year: {
          $eq: true,
        },
        environment: {
          slug: {
            $eq: environment,
          },
        },
      },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      populate: {
        location: {
          fields: [nameField, 'code', 'total_marine_area', 'total_terrestrial_area'],
        },
      },
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      fields: ['coverage', 'protected_area'],
      'pagination[limit]': 1,
    },
    {
      query: {
        select: ({ data }) => data,
        enabled: !!geometryData,
      },
    }
  );

  const formattedStats = useMemo(() => {
    if (protectionCoverageStats?.length > 0) {
      return protectionCoverageStats.map((item, idx) => {
        if (item) {
          const coverage = item?.attributes?.coverage;
          const percentage =
            coverage !== null && coverage !== undefined
              ? formatPercentage(locale, coverage, {
                  displayPercentageSign: false,
                })
              : '-';

          const pArea = item?.attributes?.protected_area;
          const protectedArea =
            pArea !== null && pArea !== undefined ? formatKM(locale, pArea) : '-';

          const tArea =
            item?.attributes?.total_area ??
            item?.attributes?.location?.data?.attributes?.[
              environment === 'marine' ? 'total_marine_area' : 'total_terrestrial_area'
            ];

          return {
            location: item.attributes.location.data.attributes[nameField],
            iso: item.attributes.location.data.attributes['code'],
            percentage,
            protectedArea,
            totalArea: +tArea,
          };
        }
        return {
          location: localizedLocationName, // default to clicked area name
          iso: locationCodes[idx],
          percentage: '-',
          protectedArea: '-',
          totalArea: '-',
        };
      });
    }

    return [
      {
        location: localizedLocationName,
        iso: locationCodes[0],
        percentage: '-',
        protectedArea: '-',
        totalArea: '-',
      },
    ];
  }, [
    environment,
    locale,
    localizedLocationName,
    locationCodes,
    nameField,
    protectionCoverageStats,
  ]);

  // handle renderer
  const handleMapRender = useCallback(() => {
    setRendered(map?.loaded() && map?.areTilesLoaded());
  }, [map]);

  const handleLocationSelected = useCallback(
    async (locationCode: string) => {
      await push(
        `${PAGES.progressTracker}/${locationCode.toUpperCase()}?${searchParams.toString()}`
      );
      setPopup({});
    },
    [push, searchParams, setPopup]
  );

  useEffect(() => {
    map?.on('render', handleMapRender);

    setRendered(map?.loaded() && map?.areTilesLoaded());

    return () => {
      map?.off('render', handleMapRender);
    };
  }, [map, handleMapRender]);

  // Close the tooltip if the layer that was clicked is not active anymore
  useEffect(() => {
    if (!activeLayers.includes(layerSlug)) {
      setPopup({});
    }
  }, [layerSlug, activeLayers, setPopup]);

  if (!geometryData) return null;

  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-sans text-xl font-black">{localizedLocationName || '-'}</h3>
      {isFetching && <div className="my-4 text-center font-mono text-xl">{t('loading')}</div>}
      {!isFetching && !protectionCoverageStats && (
        <div className="my-4 text-center font-mono">{t('no-data-available')}</div>
      )}
      {!isFetching && !!protectionCoverageStats && (
        <Accordion type="single" collapsible className="divide-y">
          {formattedStats.map((stat) => (
            <AccordionItem value={`item-${stat.iso}`} key={stat.iso}>
              <AccordionHeader>
                <AccordionTrigger className="group flex w-[100%] text-lg">
                  {stat.location}
                  <ChevronDown
                    aria-hidden
                    className="ease-[cubic-bezier(0.87,_0,_0.13,_1)] transition-transform duration-300 group-data-[state=open]:rotate-180"
                  />
                </AccordionTrigger>
              </AccordionHeader>
              <AccordionContent className="text-xs">
                <StatCard
                  environment={environment}
                  formattedStat={stat}
                  handleLocationSelected={handleLocationSelected}
                  source={source}
                />
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      )}
    </div>
  );
};

BoundariesPopup.messages = ['containers.map'];

export default BoundariesPopup;
