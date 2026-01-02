import { FC, useCallback, useMemo } from 'react';

import { Layer, Source } from 'react-map-gl';

import { useAtom } from 'jotai';

import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import {
  DRAW_STYLES,
  useMapboxDraw,
  UseMapboxDrawProps,
} from '@/components/map/draw-controls/hooks';
import { drawStateAtom } from '@/containers/map/store';

const DrawControls: FC = () => {
  const [{ active, feature }, setDrawState] = useAtom(drawStateAtom);
  console.log("Draw controls feature", feature)
  const onCreate: UseMapboxDrawProps['onCreate'] = useCallback(
    ({ features }) => {
      setDrawState((prevState) => ({
        ...prevState,
        active: false,
        status: 'success',
        feature: features[0],
      }));
    },
    [setDrawState]
  );

  const onClick: UseMapboxDrawProps['onClick'] = useCallback(() => {
    setDrawState((prevState) => ({
      ...prevState,
      status: 'drawing',
    }));
  }, [setDrawState]);

  const useMapboxDrawProps = useMemo(
    () => ({
      enabled: active,
      onCreate,
      onClick,
    }),
    [active, onClick, onCreate]
  );

  useMapboxDraw(useMapboxDrawProps);

  if (active || !feature) {
    return null;
  }

  return (
    <Source
      id="drawing"
      type="geojson"
      data={{
        type: 'FeatureCollection',
        features: [feature],
      }}
    >
      {DRAW_STYLES.filter((layer) => layer.type !== 'circle').map((layer) => (
        <Layer key={layer.id} {...layer} />
      ))}
    </Source>
  );
};

export default DrawControls;
