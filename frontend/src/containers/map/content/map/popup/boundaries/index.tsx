import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMap } from 'react-map-gl';

import { useRouter } from 'next/router';

import type { Feature } from 'geojson';
import { useAtom, useAtomValue } from 'jotai';
import { ChevronDown, ChevronRight } from 'lucide-react';
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
import { ProtectionCoverageStat } from '@/types/generated/strapi.schemas';
import { LayerTyped } from '@/types/layers';

import { POPUP_BUTTON_CONTENT_BY_SOURCE, POPUP_PROPERTIES_BY_SOURCE } from '../constants';

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

  const locationCode = useMemo(
    () => geometryData?.[POPUP_PROPERTIES_BY_SOURCE[source?.['id']]?.id],
    [geometryData, source]
  );

  const localizedLocationName = useMemo(
    () => geometryData?.[POPUP_PROPERTIES_BY_SOURCE[source?.['id']]?.name[locale]],
    [geometryData, locale, source]
  );

  const { data: protectionCoverageStats, isFetching } =
    useGetProtectionCoverageStats<ProtectionCoverageStat>(
      {
        locale,
        filters: {
          location: {
            code: locationCode,
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
            fields: [
              ...(locale === 'en' ? ['name'] : []),
              ...(locale === 'es' ? ['name_es'] : []),
              ...(locale === 'fr' ? ['name_fr'] : []),
              'code',
              'total_marine_area',
              'total_terrestrial_area',
            ],
          },
        },
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore
        fields: ['coverage', 'protected_area'],
        'pagination[limit]': 1,
      },
      {
        query: {
          select: ({ data }) => data?.[0].attributes,
          enabled: !!geometryData,
        },
      }
    );

  const formattedStats = useMemo(() => {
    if (protectionCoverageStats) {
      const percentage = formatPercentage(locale, protectionCoverageStats.coverage, {
        displayPercentageSign: false,
      });

      const protectedArea = formatKM(locale, protectionCoverageStats.protected_area);

      return {
        percentage,
        protectedArea,
      };
    }

    return {
      percentage: '-',
      protectedArea: '-',
    };
  }, [locale, protectionCoverageStats]);

  // handle renderer
  const handleMapRender = useCallback(() => {
    setRendered(map?.loaded() && map?.areTilesLoaded());
  }, [map]);

  const handleLocationSelected = useCallback(async () => {
    await push(`${PAGES.progressTracker}/${locationCode.toUpperCase()}?${searchParams.toString()}`);
    setPopup({});
  }, [push, locationCode, searchParams, setPopup]);

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
        <>
          <Accordion type="single" collapsible>
            <AccordionItem className="divide-y" value="item-1">
              <AccordionHeader>
                <AccordionTrigger className="group flex w-[100%] text-lg">
                  {protectionCoverageStats?.location?.data?.attributes?.name}
                  <ChevronDown
                    aria-hidden
                    className="ease-[cubic-bezier(0.87,_0,_0.13,_1)] transition-transform duration-300 group-data-[state=open]:rotate-180"
                  />
                </AccordionTrigger>
              </AccordionHeader>
              <AccordionContent className="text-xs">
                <div className="flex flex-col gap-2">
                  <div className="max-w-[95%] font-mono">
                    {environment === 'marine'
                      ? t('marine-conservation-coverage')
                      : t('terrestrial-conservation-coverage')}
                  </div>
                  <div className="space-x-1 font-mono tracking-tighter text-black">
                    {formattedStats.percentage !== '-' &&
                      t.rich('percentage-bold', {
                        percentage: formattedStats.percentage,
                        b1: (chunks) => (
                          <span className="text-[32px] font-bold leading-none">{chunks}</span>
                        ),
                        b2: (chunks) => <span className="text-lg">{chunks}</span>,
                      })}
                    {formattedStats.percentage === '-' && (
                      <span className="text-xl font-bold leading-none">
                        {formattedStats.percentage}
                      </span>
                    )}
                  </div>
                  <div className="space-x-1 font-mono font-medium text-black">
                    {t.rich('protected-area', {
                      br: () => <br />,
                      protectedArea: formattedStats.protectedArea,
                      totalArea: formatKM(
                        locale,
                        Number(
                          protectionCoverageStats?.location.data.attributes[
                            environment === 'marine'
                              ? 'total_marine_area'
                              : 'total_terrestrial_area'
                          ]
                        )
                      ),
                    })}
                  </div>
                </div>
                <button
                  type="button"
                  className="mt-3 block w-full border border-black px-4 py-2.5 text-center font-mono text-xs"
                  onClick={handleLocationSelected}
                >
                  {t(POPUP_BUTTON_CONTENT_BY_SOURCE[source?.['id']])}
                </button>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </>
      )}
    </div>
  );
};

BoundariesPopup.messages = ['containers.map'];

export default BoundariesPopup;
