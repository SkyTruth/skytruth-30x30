import { FC, useCallback, useMemo } from 'react';

import { useAtom, useSetAtom } from 'jotai';

import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import { useMapboxDraw, UseMapboxDrawProps } from '@/components/map/draw-controls/hooks';
import {
  bboxLocationAtom,
  customLayersAtom,
  drawStateAtom,
  modellingAtom,
  modellingCustomLayerIdAtom,
} from '@/containers/map/store';
import { createCustomLayer } from '@/lib/utils/create-custom-layer';
import { getGeoJSONBoundingBox } from '@/lib/utils/geo';

const DrawControls: FC = () => {
  const [{ active }, setDrawState] = useAtom(drawStateAtom);
  const setModellingCustomLayerId = useSetAtom(modellingCustomLayerIdAtom);
  const setCustomLayers = useSetAtom(customLayersAtom);
  const setModelling = useSetAtom(modellingAtom);
  const setBboxLocation = useSetAtom(bboxLocationAtom);

  const onCreate: UseMapboxDrawProps['onCreate'] = useCallback(
    ({ features }) => {
      const drawnFeature = features[0];
      const featureCollection = {
        type: 'FeatureCollection' as const,
        features: [drawnFeature],
      };

      // Drawn shapes are always polygons
      setCustomLayers((prev) => {
        const layer = createCustomLayer('Custom Area', featureCollection, prev, true);

        setModellingCustomLayerId(layer.id);

        const bounds = getGeoJSONBoundingBox(featureCollection);
        if (bounds) {
          setBboxLocation([...bounds] as [number, number, number, number]);
        }

        setModelling((prevState) => ({ ...prevState, active: true }));

        setDrawState((prevState) => ({
          ...prevState,
          active: false,
          status: 'success',
          source: 'draw',
        }));

        return {
          ...prev,
          [layer.id]: layer,
        };
      });
    },
    [setCustomLayers, setModellingCustomLayerId, setBboxLocation, setModelling, setDrawState]
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

  return null;
};

export default DrawControls;
