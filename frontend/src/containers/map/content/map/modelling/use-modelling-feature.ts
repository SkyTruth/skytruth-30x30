import { useMemo } from 'react';

import type { GeoJSONObject } from '@turf/turf';
import { useAtomValue } from 'jotai';

import { customLayersAtom, modellingCustomLayerIdAtom } from '@/containers/map/store';
import { extractPolygons } from '@/lib/utils/file-upload';

/**
 * The drawn or uploaded shape the Conservation Builder calculates stats for, as one polygon
 * feature, and the id of its custom layer. The feature is null when no shape is selected or
 * it has no polygons
 */
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
