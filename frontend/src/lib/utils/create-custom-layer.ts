import type { GeoJSON } from 'geojson';

import { CUSTOM_LAYER_STYLE_COLORS } from '@/constants/custom-layer-style-colors';
import type { CustomLayer } from '@/types/layers';

const DEFAULT_LAYER_STYLE = {
  opacity: 0.5,
};

export function getNextCustomLayerColor(layers: Record<string, CustomLayer>): string {
  const nextColorIndex = Object.keys(layers).length % CUSTOM_LAYER_STYLE_COLORS.length;
  return CUSTOM_LAYER_STYLE_COLORS[nextColorIndex].value;
}

export function createCustomLayer(
  name: string,
  feature: GeoJSON,
  existingLayers: Record<string, CustomLayer>
): CustomLayer {
  const id = window.crypto.randomUUID();
  const color = getNextCustomLayerColor(existingLayers);

  return {
    id,
    name,
    feature,
    isVisible: true,
    isActive: true,
    style: {
      ...DEFAULT_LAYER_STYLE,
      fillColor: color,
      lineColor: color,
    },
  };
}
