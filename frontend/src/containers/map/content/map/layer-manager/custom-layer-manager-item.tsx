import { GeoJsonLayer } from '@deck.gl/layers';
import { useAtom } from 'jotai';

import DeckJsonLayer from '@/components/map/layers/deck-json-layer';
import { customLayersAtom } from '@/containers/map/store';

type CustomLayerManagerItemProps = {
  slug: string;
};

const FILL_ALPHA = 175;
const FULL_ALPHA = 255;

/**
 * Parses a hex color to RGBA for deck.gl color props.
 * Falls back to black if the provided value cannot be parsed.
 */
const hexToRgba = (hexColor: string, alpha = FULL_ALPHA): [number, number, number, number] => {
  const trimmed = hexColor.trim();
  const withoutHash = trimmed.startsWith('#') ? trimmed.slice(1) : trimmed;
  const normalized =
    withoutHash.length === 3
      ? withoutHash
          .split('')
          .map((char) => `${char}${char}`)
          .join('')
      : withoutHash;

  if (!/^[0-9a-fA-F]{6}$/.test(normalized)) {
    return [0, 0, 0, alpha];
  }

  return [
    parseInt(normalized.slice(0, 2), 16),
    parseInt(normalized.slice(2, 4), 16),
    parseInt(normalized.slice(4, 6), 16),
    alpha,
  ];
};

const CustomLayerManagerItem = ({ slug }: CustomLayerManagerItemProps) => {
  const [customLayers] = useAtom(customLayersAtom);
  const layer = customLayers[slug];
  const defaultFillColor = hexToRgba(layer.style.fillColor, FULL_ALPHA);
  const polygonFillColor = hexToRgba(layer.style.fillColor, FILL_ALPHA);
  const polygonOutlineColor = hexToRgba(layer.style.fillColor, FULL_ALPHA);
  const lineColor = hexToRgba(layer.style.lineColor, FULL_ALPHA);

  const config = new GeoJsonLayer({
    id: `${layer.id}-layer`,
    data: layer.feature,
    visible: layer.isVisible,
    opacity: layer.style.opacity ?? 0.5,

    // Polygon fill
    filled: true,
    getFillColor: (feature) => {
      const geometryType = feature?.geometry?.type;

      if (geometryType === 'Polygon' || geometryType === 'MultiPolygon') {
        return polygonFillColor;
      }

      return defaultFillColor;
    },

    // Polygon outline
    stroked: true,
    getLineColor: (feature) => {
      const geometryType = feature?.geometry?.type;

      if (geometryType === 'Polygon' || geometryType === 'MultiPolygon') {
        return polygonOutlineColor;
      }

      if (geometryType === 'LineString' || geometryType === 'MultiLineString') {
        return lineColor;
      }

      return lineColor;
    },
    getLineWidth: 2,

    // Make line width reliable
    lineWidthUnits: 'pixels',
    lineWidthMinPixels: 1,
    lineWidthMaxPixels: 10,

    // Points
    pointType: 'circle',
    getPointRadius: 4,
    pointRadiusUnits: 'pixels',
    pointRadiusScale: 1,
    pointRadiusMinPixels: 2,
    pointRadiusMaxPixels: 15,

    parameters: {
      depthTest: false,
    },

    pickable: true,
    autoHighlight: true,

    updateTriggers: {
      getFillColor: [defaultFillColor, polygonFillColor],
      getLineColor: [lineColor, polygonOutlineColor],
    },
  });

  return <DeckJsonLayer id={`${layer.id}-layer`} beforeId={`${layer.id}-layer`} config={config} />;
};

export default CustomLayerManagerItem;
