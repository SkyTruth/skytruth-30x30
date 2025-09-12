import { useCallback, useEffect, useMemo, useState } from 'react';

import { Layer, useMap } from 'react-map-gl';

import { DeckMapboxOverlayProvider } from '@/components/map/provider';
import { CustomMapProps } from '@/components/map/types';
import LayerManagerItem from '@/containers/map/content/map/layer-manager/item';
import {
  useSyncMapLayerSettings,
  useSyncMapLayers,
} from '@/containers/map/content/map/sync-settings';

const LayerManager = ({}: { cursor: CustomMapProps['cursor'] }) => {
  const { default: map } = useMap();

  const [zoom, setZoom] = useState(map?.getZoom() ?? 1);

  const [activeLayers] = useSyncMapLayers();
  const [layersSettings] = useSyncMapLayerSettings();

  const getSettings = useCallback(
    (slug: string) => ({
      ...(layersSettings[slug] ?? { opacity: 1, visibility: true }),
      zoom,
    }),
    [layersSettings, zoom]
  );

  const layerManagerItems = useMemo(
    () =>
      activeLayers.map((slug, idx) => {
        const beforeId = idx === 0 ? 'custom-layers' : `${activeLayers[idx - 1]}-layer`;
        return (
          <LayerManagerItem
            key={slug}
            slug={slug}
            beforeId={beforeId}
            settings={getSettings(slug)}
          />
        );
      }),
    [activeLayers, getSettings]
  );

  useEffect(() => {
    const onZoom = () => {
      setZoom(map.getZoom());
    };

    map.on('zoomend', onZoom);

    return () => {
      map.off('zoomend', onZoom);
    };
  }, [map, setZoom]);

  return (
    <DeckMapboxOverlayProvider>
      <>
        {/*
          Generate all transparent backgrounds to be able to sort by layers without an error
          - https://github.com/visgl/react-map-gl/issues/939#issuecomment-625290200
        */}
        {activeLayers.map((slug, idx) => {
          const beforeId = idx === 0 ? 'custom-layers' : `${activeLayers[idx - 1]}-layer`;
          return (
            <Layer
              id={`${slug}-layer`}
              key={slug}
              type="background"
              layout={{ visibility: 'none' }}
              beforeId={beforeId}
            />
          );
        })}

        {/*
          Loop through active layers. The id is gonna be used to fetch the current layer and know how to order the layers.
          The first item will always be at the top of the layers stack
        */}
        {layerManagerItems}
      </>
    </DeckMapboxOverlayProvider>
  );
};

export default LayerManager;
