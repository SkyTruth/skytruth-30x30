import { PropsWithChildren, useEffect, useMemo, useRef } from 'react';

import debounce from 'lodash-es/debounce';

import dynamic from 'next/dynamic';

import { useAtom, useAtomValue } from 'jotai';
import { useResetAtom } from 'jotai/utils';
import { useTranslations } from 'next-intl';

import { layersImpressed } from '@/components/analytics/heap';
import Head from '@/components/head';
import Header from '@/components/header';
import MobileDisclaimerDialogStatic from '@/components/mobile-disclaimer-dialog';
import Content from '@/containers/map/content';
import Sidebar from '@/containers/map/sidebar';
import {
  drawStateAtom,
  modellingAtom,
  mapTypeAtom,
  allActiveLayersAtom,
  customLayersAtom,
} from '@/containers/map/store';
import useSyncAllLayers from '@/hooks/use-sync-all-layers';
import { FCWithMessages } from '@/types';
import { MapTypes } from '@/types/map';

const MobileDisclaimerDialog = dynamic(() => import('@/components/mobile-disclaimer-dialog'), {
  ssr: false,
});

export const LAYOUT_TYPES = {
  progress_tracker: 'progress-tracker',
  conservation_builder: 'conservation-builder',
};

export type MapLayoutProps = {
  title?: string;
  description?: string;
  type: MapTypes;
};

const MapLayout: FCWithMessages<PropsWithChildren<MapLayoutProps>> = ({
  title,
  description,
  type,
}) => {
  const t = useTranslations('layouts.map');

  const resetModelling = useResetAtom(modellingAtom);
  const resetDrawState = useResetAtom(drawStateAtom);

  const allActiveLayers = useAtomValue(allActiveLayersAtom);
  const customLayers = useAtomValue(customLayersAtom);

  const [mapType, setMapType] = useAtom(mapTypeAtom);

  const activeLayersRef = useRef(allActiveLayers);

  useEffect(() => {
    setMapType(type);
  }, [type, setMapType]);

  useSyncAllLayers(mapType);

  useEffect(() => {
    if (type !== LAYOUT_TYPES.conservation_builder) {
      resetModelling();
      resetDrawState();
    }
  }, [resetDrawState, resetModelling, type]);

  const debouncedLayersImpressed = useMemo(
    () =>
      debounce((layers: string[], currentCustomLayers: Record<string, unknown>) => {
        const loggedLayers = layers.map((layer) =>
          layer in currentCustomLayers ? 'custom' : layer
        );
        layersImpressed({ layers: loggedLayers });
      }, 500),
    []
  );

  useEffect(() => {
    if (allActiveLayers !== activeLayersRef.current) {
      debouncedLayersImpressed(allActiveLayers, customLayers);
      activeLayersRef.current = allActiveLayers;
    }
  }, [allActiveLayers, customLayers, debouncedLayersImpressed]);

  useEffect(() => {
    return () => debouncedLayersImpressed.cancel();
  }, [debouncedLayersImpressed]);

  return (
    <>
      <Head
        title={
          !title.length && type === LAYOUT_TYPES.conservation_builder
            ? t('conservation-builder')
            : title
        }
        description={description}
      />
      <MobileDisclaimerDialog />
      <div className="flex h-screen w-screen flex-col">
        <div className="flex-shrink-0">
          <Header />
        </div>
        <div className="relative flex h-full w-full flex-col overflow-hidden md:flex-row">
          {/* DESKTOP SIDEBAR */}
          <div className="hidden md:block">
            <Sidebar />
          </div>
          {/* CONTENT: MAP/TABLES */}
          <Content />
          {/* MOBILE SIDEBAR */}
          <div className="h-1/2 flex-shrink-0 overflow-hidden bg-white md:hidden">
            <Sidebar />
          </div>
        </div>
      </div>
    </>
  );
};

MapLayout.messages = [
  'layouts.map',
  ...Header.messages,
  ...Sidebar.messages,
  ...Content.messages,
  ...MobileDisclaimerDialogStatic.messages,
];

export default MapLayout;
