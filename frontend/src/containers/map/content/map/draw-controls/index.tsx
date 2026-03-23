import { useCallback, useMemo } from 'react';

import { useQueryClient } from '@tanstack/react-query';
import type { Feature } from 'geojson';
import { useAtom, useSetAtom } from 'jotai';
import { useTranslations } from 'next-intl';

import '@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css';
import {
  customLayerEngaged,
  CustomLayerActions,
  CustomLayerMethods,
} from '@/components/analytics/heap';
import { useMapboxDraw, UseMapboxDrawProps } from '@/components/map/draw-controls/hooks';
import {
  bboxLocationAtom,
  customLayersAtom,
  drawStateAtom,
  modellingAtom,
  modellingCustomLayerIdAtom,
} from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { createCustomLayer } from '@/lib/utils/create-custom-layer';
import { getGeoJSONBoundingBox } from '@/lib/utils/geo';
import { validateGeometryForModelling } from '@/lib/utils/validate-geometry-for-modelling';
import { FCWithMessages } from '@/types';

const DrawControls: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');
  const queryClient = useQueryClient();
  const [{ tab }] = useSyncMapContentSettings();
  const [{ active }, setDrawState] = useAtom(drawStateAtom);
  const [modellingState, setModelling] = useAtom(modellingAtom);
  const setModellingCustomLayerId = useSetAtom(modellingCustomLayerIdAtom);
  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const setBboxLocation = useSetAtom(bboxLocationAtom);

  const onCreate: UseMapboxDrawProps['onCreate'] = useCallback(
    ({ features }) => {
      const drawnFeature = features[0];
      const featureCollection = {
        type: 'FeatureCollection' as const,
        features: [drawnFeature],
      };

      // Create layer synchronously so it renders immediately
      const layer = createCustomLayer(t('drawn-layer'), featureCollection, customLayers, true);

      setCustomLayers((prev) => ({
        ...prev,
        [layer.id]: layer,
      }));

      const bounds = getGeoJSONBoundingBox(featureCollection) as [number, number, number, number];

      customLayerEngaged({
        action: CustomLayerActions.Create,
        bbox: bounds,
        method: CustomLayerMethods.Draw,
      });

      if (bounds) {
        setBboxLocation([...bounds]);
      }

      setDrawState((prevState) => ({
        ...prevState,
        active: false,
        status: 'success',
        source: 'draw',
      }));

      // Validate geometry server-side, then activate modelling if valid
      void (async () => {
        if (!modellingState.active) {
          setModelling((prevState) => ({ ...prevState, active: true, status: 'running' }));
        }

        const { valid } = await validateGeometryForModelling(
          queryClient,
          tab,
          layer.id,
          drawnFeature as Feature
        );

        if (!valid) {
          setCustomLayers((prev) => ({
            ...prev,
            [layer.id]: { ...prev[layer.id], canBeUsedForModelling: false },
          }));
          if (!modellingState.active) {
            setModelling({ active: false, status: 'idle', data: null, errorMessage: undefined });
          }
        } else if (!modellingState.active) {
          setModellingCustomLayerId(layer.id);
        }
      })();
    },
    [
      t,
      tab,
      customLayers,
      modellingState.active,
      queryClient,
      setCustomLayers,
      setModellingCustomLayerId,
      setBboxLocation,
      setModelling,
      setDrawState,
    ]
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

DrawControls.messages = ['containers.map-sidebar-main-panel'];

export default DrawControls;
