import { useEffect, useState, useCallback, FC } from 'react';

import ReactMapGL, { ViewState, ViewStateChangeEvent, MapEvent, useMap } from 'react-map-gl';

import { useDebounce } from 'rooks';

import { cn } from '@/lib/classnames';

import { DEFAULT_VIEW_STATE } from './constants';
import type { CustomMapProps } from './types';

// import env from '@/env.mjs';

export const Map: FC<CustomMapProps> = ({
  // * if no id is passed, react-map-gl will store the map reference in a 'default' key:
  // * https://github.com/visgl/react-map-gl/blob/ecb27c8d02db7dd09d8104e8c2011bda6aed4b6f/src/components/use-map.tsx#L18
  id = 'default',
  children,
  className,
  viewState,
  constrainedAxis,
  initialViewState,
  bounds,
  onMapViewStateChange,
  onLoad,
  ...mapboxProps
}: CustomMapProps) => {
  /**
   * REFS
   */
  const { [id]: mapRef } = useMap();

  /**
   * STATE
   */
  const [localViewState, setLocalViewState] = useState<Partial<ViewState> | null>(
    !initialViewState
      ? {
          ...DEFAULT_VIEW_STATE,
          ...viewState,
        }
      : null
  );
  const [isFlying, setFlying] = useState(false);
  const [loaded, setLoaded] = useState(false);

  /**
   * CALLBACKS
   */
  const debouncedViewStateChange = useDebounce((_viewState: Partial<ViewState>) => {
    if (onMapViewStateChange) onMapViewStateChange(_viewState);
  }, 250);

  const handleFitBounds = useCallback(() => {
    if (mapRef && bounds) {
      const { bbox, options } = bounds;

      if (bbox) {
        // enabling fly mode avoids the map to be interrupted during the bounds transition
        setFlying(true);

        mapRef.fitBounds(
          [
            [bbox[0], bbox[1]],
            [bbox[2], bbox[3]],
          ],
          options
        );
      }
    }
  }, [bounds, mapRef]);

  const handleMapMove = useCallback(
    ({ viewState: _viewState }: ViewStateChangeEvent) => {
      const newViewState = {
        ..._viewState,
        latitude: constrainedAxis === 'y' ? localViewState?.latitude : _viewState.latitude,
        longitude: constrainedAxis === 'x' ? localViewState?.longitude : _viewState.longitude,
      };
      setLocalViewState(newViewState);
      debouncedViewStateChange(newViewState);
    },
    [constrainedAxis, localViewState?.latitude, localViewState?.longitude, debouncedViewStateChange]
  );

  const handleMapLoad = useCallback(
    (e: MapEvent) => {
      setLoaded(true);

      if (onLoad) {
        onLoad(e);
      }
    },
    [onLoad]
  );

  useEffect(() => {
    if (mapRef && bounds) {
      handleFitBounds();
    }
  }, [mapRef, bounds, handleFitBounds]);

  useEffect(() => {
    setLocalViewState((prevViewState) => ({
      ...prevViewState,
      ...viewState,
    }));
  }, [viewState]);

  useEffect(() => {
    if (!bounds) return undefined;

    const { options } = bounds;
    const animationDuration = options?.duration || 0;
    let timeoutId: number;

    if (isFlying) {
      timeoutId = window.setTimeout(() => {
        setFlying(false);
      }, animationDuration);
    }

    return () => {
      if (timeoutId) {
        window.clearInterval(timeoutId);
      }
    };
  }, [bounds, isFlying]);

  return (
    <div className={cn('relative z-0 h-full w-full', className)}>
      <ReactMapGL
        id={id}
        initialViewState={initialViewState}
        mapboxAccessToken={process.env.NEXT_PUBLIC_MAPBOX_API_TOKEN}
        onMove={handleMapMove}
        onLoad={handleMapLoad}
        mapStyle="mapbox://styles/skytruth/clnud2d3100nr01pl3b4icpyw"
        preserveDrawingBuffer={true}
        dragRotate={false}
        touchZoomRotate={false}
        transformRequest={(url) => {
          // Global Fishing Watch tilers require authorization token and we're also passing the past
          // 12 months as a parameter
          if (url.startsWith('https://gateway.api.globalfishingwatch.org/')) {
            return {
              url,
              headers: {
                Authorization: `Bearer ${process.env.NEXT_PUBLIC_GLOBAL_FISHING_WATCH_TOKEN}`,
              },
            };
          }

          return null;
        }}
        {...mapboxProps}
        {...localViewState}
      >
        {!!mapRef && loaded && children}
      </ReactMapGL>
    </div>
  );
};

export default Map;
export { default as ZoomControls } from './zoom-controls';
export { default as Screenshot } from './screenshot';
export { default as Attributions } from './attributions';
