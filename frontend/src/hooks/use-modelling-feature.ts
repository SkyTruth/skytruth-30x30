import { useMemo } from 'react';

import type { GeoJSONObject } from '@turf/turf';
import { useAtomValue } from 'jotai';

import { customLayersAtom, modellingCustomLayerIdAtom } from '@/containers/map/store';
import { extractPolygons } from '@/lib/utils/file-upload';

const useModellingFeature = () => {
  const layerId = useAtomValue(modellingCustomLayerIdAtom);
  const customLayers = useAtomValue(customLayersAtom);

  const layer = layerId ? customLayers[layerId] : null;

  const feature = useMemo(() => {
    if (!layer) return null;
    try {
      return extractPolygons(layer.feature as GeoJSONObject).feature;
    } catch {
      return null;
    }
  }, [layer]);

  return { feature, layerId };
};

export default useModellingFeature;
