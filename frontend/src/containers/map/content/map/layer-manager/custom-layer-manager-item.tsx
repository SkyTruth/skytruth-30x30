import { GeoJsonLayer } from '@deck.gl/layers';
import { useAtom } from 'jotai';

import DeckJsonLayer from '@/components/map/layers/deck-json-layer';
import { customLayersAtom } from '@/containers/map/store';

type CustomLayerManagerItemProps = {
  slug: string;
};

const CustomLayerManagerItem = ({ slug }: CustomLayerManagerItemProps) => {
  const [customLayers] = useAtom(customLayersAtom);
  const layer = customLayers[slug];

  const config = new GeoJsonLayer({
    id: `${layer.id}-layer`,
    data: layer.feature,
    visible: layer.isVisible,
    opacity: 0.5,

    // Polygon fill
    filled: true,
    getFillColor: () => {
      const hex = layer.style.fillColor;
      return hex.match(/[0-9a-f]{2}/g).map((x) => parseInt(x, 16));
    },

    // Polygon outline
    stroked: true,
    getLineColor: () => {
      const hex = layer.style.lineColor;
      return hex.match(/[0-9a-f]{2}/g).map((x) => parseInt(x, 16));
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
  });

  return <DeckJsonLayer id={`${layer.id}-layer`} beforeId={`${layer.id}-layer`} config={config} />;
};

export default CustomLayerManagerItem;
