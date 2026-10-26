import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMap } from 'react-map-gl';

import type { Feature } from 'geojson';
import { useAtomValue } from 'jotai';
import { useLocale } from 'next-intl';

import { layersInteractiveIdsAtom, popupAtom } from '@/containers/map/store';
import { format } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { LayerTyped, InteractionConfig } from '@/types/layers';

import CardAccordion from '../CardAccordion';

type ClickValue = InteractionConfig['events'][number]['values'][number];
type Properties = NonNullable<Feature['properties']>;

const formatLabel = (label: string) =>
  label
    .toLowerCase()
    .split(' ')
    .map((word) => word.charAt(0).toUpperCase() + word.substring(1))
    .join(' ');

const GenericCard = ({ properties, values }: { properties: Properties; values: ClickValue[] }) => {
  const locale = useLocale();

  return (
    <dl className="space-y-2">
      {values.map(({ key, label, format: customFormat }) => (
        <div key={key}>
          <dt className="mt-4 font-mono">{formatLabel(label)}</dt>
          <dd className="font-mono first-letter:uppercase">
            {customFormat && format({ locale, value: properties[key], ...customFormat })}
            {!customFormat && properties[key]}
          </dd>
        </div>
      ))}
    </dl>
  );
};

const GenericPopup: FCWithMessages<InteractionConfig & { layerSlug: string }> = ({
  layerSlug,
  ...restConfig
}) => {
  const [rendered, setRendered] = useState(false);
  const DATA_REF = useRef<Properties[]>([]);
  const { default: map } = useMap();
  const { events } = restConfig;

  const locale = useLocale();

  const popup = useAtomValue(popupAtom);
  const layersInteractiveIds = useAtomValue(layersInteractiveIdsAtom);

  const { data: layerQuery, isFetching } = useGetLayers<{
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
            (ev) => ev.type === 'click'
          ),
        }),
      },
    }
  );

  let source = undefined;

  if (!isFetching) {
    source = layerQuery?.source;
  }

  // Every feature of this source under the click. Mapbox returns one entry per
  // style layer and tile hit, so the same feature is kept once.
  const DATA = useMemo(() => {
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

      const byKey = new Map<string, Properties>();
      query
        .filter((feature) => feature.source === source.id)
        .forEach((feature) => {
          byKey.set(String(feature.id ?? JSON.stringify(feature.properties)), feature.properties);
        });

      DATA_REF.current = Array.from(byKey.values());
    }

    return DATA_REF.current;
  }, [popup, source, layersInteractiveIds, map, rendered]);

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

  const values = events.find((ev) => ev.type === 'click')?.values ?? [];
  const nameKey = values.find((value) => value.label === 'Name')?.key;
  const restValues = values.filter((value) => value.label !== 'Name');

  if (DATA.length === 1) {
    return (
      <div className="space-y-2">
        {nameKey && <h3 className="line-clamp-2 text-xl font-semibold">{DATA[0][nameKey]}</h3>}
        <GenericCard properties={DATA[0]} values={restValues} />
      </div>
    );
  }

  return (
    <CardAccordion
      items={DATA.map((properties, index) => ({
        id: String(index),
        title: nameKey ? properties[nameKey] : null,
        content: <GenericCard properties={properties} values={restValues} />,
      }))}
    />
  );
};

GenericPopup.messages = ['containers.map'];

export default GenericPopup;
