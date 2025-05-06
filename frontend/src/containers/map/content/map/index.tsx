import { ComponentProps, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMap } from 'react-map-gl';

import dynamic from 'next/dynamic';

import { useAtom, useAtomValue } from 'jotai';
import { useLocale } from 'next-intl';

import Map, { ZoomControls, Attributions } from '@/components/map';
import { DEFAULT_VIEW_STATE } from '@/components/map/constants';
import DrawControls from '@/containers/map/content/map/draw-controls';
import LabelsManager from '@/containers/map/content/map/labels-manager';
import LayersToolbox from '@/containers/map/content/map/layers-toolbox';
import Modelling from '@/containers/map/content/map/modelling';
import Popup from '@/containers/map/content/map/popup';
import BoundariesPopup from '@/containers/map/content/map/popup/boundaries';
import GenericPopup from '@/containers/map/content/map/popup/generic';
import ProtectedAreaPopup from '@/containers/map/content/map/popup/protected-area';
import { useSyncMapLayers, useSyncMapSettings } from '@/containers/map/content/map/sync-settings';
import {
  drawStateAtom,
  layersInteractiveAtom,
  layersInteractiveIdsAtom,
  popupAtom,
} from '@/containers/map/store';
import useMapBounds from '@/hooks/useMapBounds';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { LayerTyped } from '@/types/layers';

const LayerManager = dynamic(() => import('@/containers/map/content/map/layer-manager'), {
  ssr: false,
});

const MainMap: FCWithMessages = () => {
  const locale = useLocale();

  const [{ bbox: URLBbox }, setMapSettings] = useSyncMapSettings();
  const [mapLayers, setMapLayers] = useSyncMapLayers();
  const bounds = useMapBounds();
  const { default: map } = useMap();

  const drawState = useAtomValue(drawStateAtom);
  const layersInteractive = useAtomValue(layersInteractiveAtom);
  const layersInteractiveIds = useAtomValue(layersInteractiveIdsAtom);

  const [popup, setPopup] = useAtom(popupAtom);

  const [cursor, setCursor] = useState<'grab' | 'crosshair' | 'pointer'>('grab');
  
  const hoveredPolygonId = useRef<Parameters<typeof map.setFeatureState>[0] | null>(null);
  const mountedRef = useRef(false);
  const previousDefaultLayersRef = useRef(null);


  const { data: layersInteractiveData } = useGetLayers(
    {
      locale,
      filters: {
        slug: {
          $in: layersInteractive,
        },
      },
    },
    {
      query: {
        enabled: !!layersInteractive.length,
        select: ({ data }) => data,
      },
    }
  );

  const { data: defaultLayers } = useGetLayers(
    {
      locale,
      fields: 'slug',
      filters: {
        default: {
          $eq: true,
        },
      },
      // Makes sure that the default interactive layers are displayed on top so that their
      // highlighted states are fully visible
      sort: 'interaction_config',
    },
    {
      query: {
        select: ({ data }) => data.map(({ attributes }) => attributes?.slug),
      },
    }
  );

  // Once we have fetched from the CMS which layers are active by default, we set toggle them on, if
  // there are already no layers in the URL and we've just fetched
  // That last condition is important because we don't want to activate the default layers if the
  // user manually remove all the layers from the map
  useEffect(() => {
    if (!previousDefaultLayersRef.current && defaultLayers && mapLayers.length === 0) {
      setMapLayers(defaultLayers);
    }

    previousDefaultLayersRef.current = defaultLayers;

  }, [mapLayers, setMapLayers, defaultLayers]);

  const safelyResetFeatureState = useCallback(() => {
    if (!hoveredPolygonId.current) {
      return;
    }

    const isSourceStillAvailable = !!map.getSource(hoveredPolygonId.current.source);

    if (isSourceStillAvailable) {
      map.setFeatureState(
        {
          source: hoveredPolygonId.current.source,
          id: hoveredPolygonId.current.id,
          sourceLayer: hoveredPolygonId.current.sourceLayer,
        },
        { hover: false }
      );
    }
  }, [map]);

  const safelySetFeatureState = useCallback(
    (feature: mapboxgl.MapboxGeoJSONFeature) => {
      const isSameId = !hoveredPolygonId.current || hoveredPolygonId.current.id === feature.id;

      const isSameSource =
        !hoveredPolygonId.current || hoveredPolygonId.current.source === feature.source;

      const isSameSourceLayer =
        !hoveredPolygonId.current || hoveredPolygonId.current.sourceLayer === feature.sourceLayer;

      if (!isSameId || !isSameSource || !isSameSourceLayer) {
        safelyResetFeatureState();
      }

      map.setFeatureState(
        {
          source: feature.source,
          id: feature.id,
          sourceLayer: feature.sourceLayer,
        },
        { hover: true }
      );

      hoveredPolygonId.current = feature;
    },
    [map, safelyResetFeatureState]
  );

  const handleMoveEnd = useCallback(() => {
    setMapSettings((prev) => ({
      ...prev,
      bbox: map
        .getBounds()
        .toArray()
        .flat()
        .map((b) => parseFloat(b.toFixed(2))) as typeof URLBbox,
    }));
  }, [map, setMapSettings]);

  const handleMapClick = useCallback(
    (e: Parameters<ComponentProps<typeof Map>['onClick']>[0]) => {
      if (drawState.active) return null;

      if (popup?.features?.length) {
        safelyResetFeatureState();
        setPopup({});
      }

      if (
        layersInteractive.length &&
        layersInteractiveData.some((l) => {
          const attributes = l.attributes as LayerTyped;
          return attributes?.interaction_config?.events.some((ev) => ev.type === 'click');
        })
      ) {
        const p = Object.assign({}, e, { features: e.features ?? [] });
        setPopup(p);
      }
    },
    [
      drawState.active,
      popup?.features?.length,
      layersInteractive.length,
      layersInteractiveData,
      safelyResetFeatureState,
      setPopup,
    ]
  );

  const handleMouseMove = useCallback(
    (e: Parameters<ComponentProps<typeof Map>['onMouseOver']>[0]) => {
      if (!e.features.length) {
        setPopup({});
      }

      if (e?.features?.length > 0) {
        if (!drawState.active) {
          setCursor('pointer');
        }

        if (e.type === 'mousemove') {
          setPopup({ ...e });
        }

        if (e.features?.[0]) {
          safelySetFeatureState(e.features?.[0]);
        }
      } else {
        if (!drawState.active) {
          setCursor('grab');
        }
      }
    },
    [setPopup, drawState.active, safelySetFeatureState]
  );

  const handleMouseOut = useCallback(() => {
    safelyResetFeatureState();

    if (popup?.type !== 'click') {
      // If the popup was opened through a click, we keep it open so that the user can eventually
      // interact with it's content
      setPopup({});
    }
  }, [safelyResetFeatureState, popup, setPopup]);

  const initialViewState: ComponentProps<typeof Map>['initialViewState'] = useMemo(() => {
    if (URLBbox) {
      return {
        ...DEFAULT_VIEW_STATE,
        bounds: URLBbox as ComponentProps<typeof Map>['initialViewState']['bounds'],
      };
    }

    return DEFAULT_VIEW_STATE;
  }, [URLBbox]);

  useEffect(() => {
    setCursor(drawState.active ? 'crosshair' : 'grab');
  }, [drawState.active]);

  useEffect(() => {
    mountedRef.current = true;
  }, []);

  const disableMouseMove = popup.type === 'click' && popup.features?.length;

  return (
    <div className="absolute left-0 h-full w-full border-b border-r border-black">
      <Map
        initialViewState={initialViewState}
        bounds={bounds}
        interactiveLayerIds={!drawState.active && !drawState.feature ? layersInteractiveIds : []}
        onClick={handleMapClick}
        onMoveEnd={handleMoveEnd}
        onMouseMove={!disableMouseMove && handleMouseMove}
        onMouseOut={handleMouseOut}
        attributionControl={false}
        cursor={cursor}
      >
        <>
          <Popup />
          <LabelsManager />
          <LayersToolbox />
          <ZoomControls />
          <DrawControls />
          <LayerManager cursor={cursor} />
          <Modelling />
          <Attributions />
        </>
      </Map>
    </div>
  );
};

MainMap.messages = [
  'containers.map',
  ...Popup.messages,
  ...LayersToolbox.messages,
  ...ZoomControls.messages,
  // Indirectly imported by the layer manager
  ...GenericPopup.messages,
  ...ProtectedAreaPopup.messages,
  ...BoundariesPopup.messages,
];

export default MainMap;
