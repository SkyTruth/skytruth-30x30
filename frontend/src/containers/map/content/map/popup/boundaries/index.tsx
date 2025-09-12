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
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { LayerTyped } from '@/types/layers';

import { POPUP_PROPERTIES_BY_SOURCE } from '../constants';

import useFormattedStats from './hooks';
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

  const locationCodes = useMemo(() => {
    const locKeys = POPUP_PROPERTIES_BY_SOURCE[source?.['id']]?.ids ?? [];
    const codes = [];
    locKeys.forEach((key: string) => geometryData?.[key] && codes.push(geometryData[key]));

    return codes;
  }, [geometryData, source]);

  const localizedLocationName = useMemo(
    () => geometryData?.[POPUP_PROPERTIES_BY_SOURCE[source?.['id']]?.name[locale]],
    [geometryData, locale, source]
  );

  const [formattedStats, isFetching] = useFormattedStats(
    locationCodes,
    environment,
    !!geometryData
  );

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

  const renderStats = () => {
    return formattedStats.length === 1 ? (
      <StatCard
        environment={environment}
        formattedStat={formattedStats[0]}
        handleLocationSelected={handleLocationSelected}
        source={source}
      />
    ) : (
      <Accordion type="single" collapsible className="divide-y">
        {formattedStats.map((stat) => (
          <AccordionItem value={`item-${stat.iso}`} key={stat.iso}>
            <AccordionHeader>
              <AccordionTrigger className="text-m group flex grid w-[100%] grid-cols-6 justify-items-start gap-4 text-left">
                <span className="col-span-5 col-start-1 font-semibold">{stat.location}</span>
                <ChevronDown
                  aria-hidden
                  className="ease-&lsqb;cubic-bezier(0.87,_0,_0.13,_1)&rsqb; transition-transform duration-300 group-data-[state=open]:rotate-180"
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
    );
  };

  if (!geometryData) return null;

  return (
    <div className="flex flex-col gap-2">
      <h3 className="font-sans text-xl font-black">{localizedLocationName || '-'}</h3>
      {isFetching && <div className="my-4 text-center font-mono text-xl">{t('loading')}</div>}
      {!isFetching && !formattedStats && (
        <div className="my-4 text-center font-mono">{t('no-data-available')}</div>
      )}
      {!isFetching && !!formattedStats && renderStats()}
    </div>
  );
};

BoundariesPopup.messages = ['containers.map'];

export default BoundariesPopup;
