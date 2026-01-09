import { useCallback, useEffect, useMemo, useState } from 'react';

import { Layer, useMap } from 'react-map-gl';

import { useAtom } from 'jotai';

import { DeckMapboxOverlayProvider } from '@/components/map/provider';
import { CustomMapProps } from '@/components/map/types';
import LayerManagerItem from '@/containers/map/content/map/layer-manager/item';
import {
  useSyncMapLayerSettings,
  useSyncMapLayers,
} from '@/containers/map/content/map/sync-settings';
import { customLayersAtom } from '@/containers/map/store';

import CustomLayerManagerItem from './CustomLayerManagerItem';

const LayerManager = ({}: { cursor: CustomMapProps['cursor'] }) => {
  const { default: map } = useMap();

  const [zoom, setZoom] = useState(map?.getZoom() ?? 1);

  const [activeLayers] = useSyncMapLayers();
  const [layersSettings] = useSyncMapLayerSettings();

  const [customLayers] = useAtom(customLayersAtom);

  const [allActiveLayers, setAllActiveLayers] = useState([]);

  useEffect(() => {
    const customActiveLayers = customLayers.filter((layer) => !!layer.active);
    const currentActiveLayers = [...activeLayers, ...customActiveLayers];

    setAllActiveLayers(currentActiveLayers);
  }, [activeLayers, customLayers]);

  const getSettings = useCallback(
    (slug: string) => ({
      ...(layersSettings[slug] ?? { opacity: 1, visibility: true }),
      zoom,
    }),
    [layersSettings, zoom]
  );

  const getLayerId = (layer: string | { id: number }) => {
    return typeof layer === 'string' ? layer : String(layer.id);
  };

  const layerManagerItems = useMemo(() => {
    return allActiveLayers.map((layer, idx) => {
      const beforeId =
        idx === 0 ? 'custom-layers' : `${getLayerId(allActiveLayers[idx - 1])}-layer`;

      if (typeof layer === 'string') {
        return (
          <LayerManagerItem
            key={layer}
            slug={layer}
            beforeId={beforeId}
            settings={getSettings(layer)}
          />
        );
      }
      return <CustomLayerManagerItem key={layer.id} layer={layer} />;
    });
  }, [allActiveLayers, getSettings]);

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
        {allActiveLayers.map((layer, idx) => {
          const beforeId =
            idx === 0 ? 'custom-layers' : `${getLayerId(allActiveLayers[idx - 1])}-layer`;
          const id = getLayerId(layer);
          return (
            <Layer
              id={`${id}-layer`}
              key={id}
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
