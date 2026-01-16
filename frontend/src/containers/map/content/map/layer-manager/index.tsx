import { useCallback, useEffect, useMemo, useState } from 'react';

import { Layer, useMap } from 'react-map-gl';

import { useAtom } from 'jotai';

import { DeckMapboxOverlayProvider } from '@/components/map/provider';
import { CustomMapProps } from '@/components/map/types';
import LayerManagerItem from '@/containers/map/content/map/layer-manager/item';
import { useSyncMapLayerSettings } from '@/containers/map/content/map/sync-settings';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';

import CustomLayerManagerItem from './custom-layer-manager-item';

const LayerManager = ({}: { cursor: CustomMapProps['cursor'] }) => {
  const { default: map } = useMap();

  const [zoom, setZoom] = useState(map?.getZoom() ?? 1);

  const [layersSettings] = useSyncMapLayerSettings();

  const [allActiveLayers] = useAtom(allActiveLayersAtom);
  const [customLayers] = useAtom(customLayersAtom);

  const getSettings = useCallback(
    (slug: string) => ({
      ...(layersSettings[slug] ?? { opacity: 1, visibility: true }),
      zoom,
    }),
    [layersSettings, zoom]
  );

  const layerManagerItems = useMemo(() => {
    return allActiveLayers.map((slug, idx) => {
      const beforeId = idx === 0 ? 'custom-layers' : `${allActiveLayers[idx - 1]}-layer`;

      if (!customLayers[slug]) {
        return (
          <LayerManagerItem
            key={slug}
            slug={slug}
            beforeId={beforeId}
            settings={getSettings(slug)}
          />
        );
      }
      return <CustomLayerManagerItem key={slug} slug={slug} />;
    });
  }, [allActiveLayers, customLayers, getSettings]);

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
        {allActiveLayers.map((slug, idx) => {
          const beforeId = idx === 0 ? 'custom-layers' : `${allActiveLayers[idx - 1]}-layer`;

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
