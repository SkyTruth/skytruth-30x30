import { ComponentProps, useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useMap } from 'react-map-gl';

import dynamic from 'next/dynamic';
import { useParams } from 'next/navigation';

import { useAtom, useAtomValue } from 'jotai';
import { useResetAtom } from 'jotai/utils';
import { useLocale } from 'next-intl';

import Map, { ZoomControls, Attributions } from '@/components/map';
import { DEFAULT_VIEW_STATE } from '@/components/map/constants';
import { CustomMapProps } from '@/components/map/types';
import DrawControls from '@/containers/map/content/map/draw-controls';
import LabelsManager from '@/containers/map/content/map/labels-manager';
import LayersToolbox from '@/containers/map/content/map/layers-toolbox';
import Modelling from '@/containers/map/content/map/modelling';
import Popup from '@/containers/map/content/map/popup';
import BoundariesPopup from '@/containers/map/content/map/popup/boundaries';
import GenericPopup from '@/containers/map/content/map/popup/generic';
import ProtectedAreaPopup from '@/containers/map/content/map/popup/protected-area';
import { useSyncMapLayers, useSyncMapSettings } from '@/containers/map/content/map/sync-settings';
import { layersAtom, sidebarAtom } from '@/containers/map/store';
import {
  bboxLocationAtom,
  drawStateAtom,
  layersInteractiveAtom,
  layersInteractiveIdsAtom,
  popupAtom,
} from '@/containers/map/store';
import { FCWithMessages } from '@/types';
import { useGetLayers } from '@/types/generated/layer';
import { useGetLocations } from '@/types/generated/location';
import { LayerTyped } from '@/types/layers';

const LayerManager = dynamic(() => import('@/containers/map/content/map/layer-manager'), {
  ssr: false,
});

const MainMap: FCWithMessages = () => {
  const locale = useLocale();

  const [{ bbox: URLBbox }, setMapSettings] = useSyncMapSettings();
  const [, setMapLayers] = useSyncMapLayers();
  const { default: map } = useMap();
  const drawState = useAtomValue(drawStateAtom);
  const isSidebarOpen = useAtomValue(sidebarAtom);
  const isLayersPanelOpen = useAtomValue(layersAtom);
  const [popup, setPopup] = useAtom(popupAtom);
  const params = useParams();
  const [locationBbox, setLocationBbox] = useAtom(bboxLocationAtom);
  const resetLocationBbox = useResetAtom(bboxLocationAtom);
  const hoveredPolygonId = useRef<Parameters<typeof map.setFeatureState>[0] | null>(null);
  const [cursor, setCursor] = useState<'grab' | 'crosshair' | 'pointer'>('grab');

  const locationCode = params?.locationCode || 'GLOB';

  const locationsQuery = useGetLocations(
    {
      locale,
      filters: {
        code: locationCode,
      },
    },
    {
      query: {
        queryKey: ['locations', locationCode],
        select: ({ data }) => data?.[0]?.attributes,
      },
    }
  );

  const layersInteractive = useAtomValue(layersInteractiveAtom);
  const layersInteractiveIds = useAtomValue(layersInteractiveIdsAtom);

  const { data: layersInteractiveData } = useGetLayers(
    {
      locale,
      filters: {
        id: {
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
      fields: 'id',
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
        select: ({ data }) => data.map(({ id }) => id),
      },
    }
  );

  // Once we have fetched from the CMS which layers are active by default, we set toggle them on
  useEffect(() => {
    if (defaultLayers) {
      setMapLayers(defaultLayers);
    }
  }, [setMapLayers, defaultLayers]);

  useEffect(() => {
    setLocationBbox(locationsQuery?.data?.marine_bounds as CustomMapProps['bounds']['bbox']);
  }, [locationCode, locationsQuery, setLocationBbox]);

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

    if (locationsQuery.data && locationsQuery.data?.code !== 'GLOB') {
      return {
        ...DEFAULT_VIEW_STATE,
        bounds: locationsQuery.data?.marine_bounds as ComponentProps<
          typeof Map
        >['initialViewState']['bounds'],
        padding: {
          top: 0,
          bottom: 0,
          left: isSidebarOpen ? 430 : 0,
          right: 0,
        },
      };
    }

    return DEFAULT_VIEW_STATE;
  }, [URLBbox, isSidebarOpen, locationsQuery.data]);

  const bounds: ComponentProps<typeof Map>['bounds'] = useMemo(() => {
    if (!locationBbox) return null;

    const padding = 20;

    let leftPadding = padding;
    if (typeof window !== 'undefined' && window?.innerWidth > 430) {
      if (isSidebarOpen) {
        leftPadding += 460;
      }

      if (isLayersPanelOpen) {
        leftPadding += 280;
      }
    }

    return {
      bbox: locationBbox as ComponentProps<typeof Map>['bounds']['bbox'],
      options: {
        padding: {
          top: padding,
          bottom: padding,
          left: leftPadding,
          right: padding,
        },
      },
    };
  }, [locationBbox, isSidebarOpen, isLayersPanelOpen]);

  useEffect(() => {
    setCursor(drawState.active ? 'crosshair' : 'grab');
  }, [drawState.active]);

  useEffect(() => {
    return () => {
      resetLocationBbox();
    };
  }, [resetLocationBbox]);

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
