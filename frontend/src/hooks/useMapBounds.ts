'use client';

import { ComponentProps, useEffect, useRef, useState } from 'react';

import { useAtomValue } from 'jotai';

import Map from '@/components/map';
import { useSyncMapSettings } from '@/containers/map/content/map/sync-settings';
import { bboxLocationAtom, layersAtom, sidebarAtom } from '@/containers/map/store';

const getBoundsPadding = (isSidebarOpen: boolean, isLayersPanelOpen: boolean) => {
  const padding = {
    top: 20,
    right: 20,
    bottom: 20,
    left: 20,
  };

  if (window.innerWidth > 430) {
    if (isSidebarOpen) {
      padding.left += 460;
    }

    if (isLayersPanelOpen) {
      padding.left += 280;
    }
  }

  return padding;
};

export default function useMapBounds() {
  const [bounds, setBounds] = useState<ComponentProps<typeof Map>['bounds']>(null);

  const [{ bbox: URLBbox }] = useSyncMapSettings();

  const bboxLocation = useAtomValue(bboxLocationAtom);
  const isSidebarOpen = useAtomValue(sidebarAtom);
  const isLayersPanelOpen = useAtomValue(layersAtom);

  const previousBboxLocationRef = useRef(bboxLocation);
  const previousIsSidebarOpenRef = useRef(isSidebarOpen);

  // If `bboxLocation` changes, then we provide new bounds
  useEffect(() => {
    const hasBboxLocationChanged =
      bboxLocation !== previousBboxLocationRef.current && !!previousBboxLocationRef.current;

    if (hasBboxLocationChanged) {
      setBounds({
        bbox: bboxLocation,
        options: {
          padding: getBoundsPadding(isSidebarOpen, isLayersPanelOpen),
        },
      });
    }

    previousBboxLocationRef.current = bboxLocation;
  }, [setBounds, bboxLocation, isSidebarOpen, isLayersPanelOpen]);

  // If the sidebar is expanded/collapsed, provide updated bounds
  useEffect(() => {
    const hasIsSidebarOpenChanged =
      isSidebarOpen !== previousIsSidebarOpenRef.current &&
      previousIsSidebarOpenRef.current !== null;

    if (hasIsSidebarOpenChanged) {
      setBounds({
        bbox: URLBbox as [number, number, number, number],
        options: {
          padding: getBoundsPadding(isSidebarOpen, isLayersPanelOpen),
        },
      });
    }

    previousIsSidebarOpenRef.current = isSidebarOpen;
  }, [URLBbox, setBounds, isSidebarOpen, isLayersPanelOpen]);

  return bounds;
}
