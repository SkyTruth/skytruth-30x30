import { GeoJsonLayer } from '@deck.gl/layers';
import { useAtom } from 'jotai';

import DeckJsonLayer from '@/components/map/layers/deck-json-layer';
import { customLayersAtom } from '@/containers/map/store';

interface CustomLayerManagerItemProps {
  slug: string;
}

const CustomLayerManagerItem = ({ slug }: CustomLayerManagerItemProps) => {
  const [customLayers] = useAtom(customLayersAtom);
  const layer = customLayers[slug];

  const config = new GeoJsonLayer({
    id: `${layer.id}-layer`,
    data: layer.feature,
    visible: layer.isVisible,

    // Polygon fill
    filled: true,
    getFillColor: [0, 0, 0, 70],

    // Polygon outline
    stroked: true,
    getLineColor: [0, 0, 255, 255],
    getLineWidth: 2,

    // Make line width reliable
    lineWidthUnits: 'pixels',
    lineWidthMinPixels: 1,
    lineWidthMaxPixels: 10,

    // Quality improvements
    parameters: {
      depthTest: false, // ensures lines aren't hidden by fill depth
    },

    pickable: true,
    autoHighlight: true,
  });

  return <DeckJsonLayer id={`${layer.id}-layer`} beforeId={`${layer.id}-layer`} config={config} />;
};

export default CustomLayerManagerItem;
