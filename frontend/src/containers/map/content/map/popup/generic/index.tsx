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

const GenericPopup: FCWithMessages<InteractionConfig & { layerSlug: string }> = ({
  layerSlug,
  ...restConfig
}) => {
  const [rendered, setRendered] = useState(false);
  const DATA_REF = useRef<Feature['properties'] | undefined>();
  const { default: map } = useMap();
  const { events } = restConfig;

  const locale = useLocale();

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
          $eq: layerSlug
      },
    },
      populate: 'metadata',
    },
    {
      query: {
        select: ({ data }) => ({
          source: (data[0].attributes as LayerTyped).config?.source,
          click: (data[0].attributes as LayerTyped)?.interaction_config?.events.find(
            (ev) => ev.type === 'click'
          ),
        }),
      },
    }
  );

  const { source } = layerQuery.data;

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

      const d = query.find((d) => {
        return d.source === source.id;
      })?.properties;

      DATA_REF.current = d;

      if (d) {
        return DATA_REF.current;
      }
    }

    return DATA_REF.current;
  }, [popup, source, layersInteractiveIds, map, rendered]);

  // handle renderer
  const handleMapRender = useCallback(() => {
    setRendered(map?.loaded() && map?.areTilesLoaded());
  }, [map]);

  const formatLabel = (label) =>
    label
      .toLowerCase()
      .split(' ')
      .map((s) => s.charAt(0).toUpperCase() + s.substring(1))
      .join(' ');

  useEffect(() => {
    map?.on('render', handleMapRender);

    setRendered(map?.loaded() && map?.areTilesLoaded());

    return () => {
      map?.off('render', handleMapRender);
    };
  }, [map, handleMapRender]);

  if (!DATA) return null;

  const values = events.find((ev) => ev.type === 'click')?.values;
  const name = values?.find((v) => v.label === 'Name');
  const restValues = (values?.filter((v) => v.label !== 'Name') ?? []).map(
    ({ label, ...rest }) => ({
      label: formatLabel(label),
      ...rest,
    })
  );

  return (
    <>
      <div className="space-y-2">
        {name && <h3 className="line-clamp-2 text-xl font-semibold">{DATA?.[name.key]}</h3>}
        <dl className="space-y-2">
          {restValues.map(({ key, label, format: customFormat }) => (
            <div key={key}>
              <dt className="mt-4 font-mono">{label}</dt>
              <dd className="font-mono first-letter:uppercase">
                {customFormat && format({ locale, value: DATA[key], ...customFormat })}
                {!customFormat && DATA[key]}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </>
  );
};

GenericPopup.messages = ['containers.map'];

export default GenericPopup;
