import { FC } from 'react';

import { Layer, Source } from 'react-map-gl';

import { useAtom } from 'jotai';

import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { DRAW_STYLES } from '@/components/map/draw-controls/hooks';
import { userLayersAtom } from '@/containers/map/store';

const LayerUploadControls: FC = () => {
  const [userLayers] = useAtom(userLayersAtom);

  if (!userLayers.length) {
    return null;
  }

  return (
    <Source id="user-layer" type="geojson" data={userLayers[0].feature}>
      {DRAW_STYLES.filter((layer) => layer.type !== 'circle').map((layer) => (
        <Layer key={layer.id} {...layer} />
      ))}
    </Source>
  );
};

export default LayerUploadControls;
