import { useCallback, useEffect, useMemo, useRef } from 'react';

import Router from 'next/router';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';

import useDatasetsByEnvironment from './use-datasets-by-environment';

function useDefaultLayersForTab() {
  const [datasets] = useDatasetsByEnvironment();

  const defaultLayerSlugs = useMemo(() => {
    const datasetsDefaultLayerIds = (datasets = []) => {
      return datasets.reduce((acc, dataset) => {
        const layersData = dataset?.layers;

        const defaultLayerSlugs = layersData.reduce(
          (acc, layers) => (layers?.default ? [...acc, layers.slug] : acc),
          []
        );
        return [...acc, ...defaultLayerSlugs];
      }, []);
    };

    return {
      terrestrial: datasetsDefaultLayerIds(datasets.terrestrial),
      marine: datasetsDefaultLayerIds(datasets.marine),
      basemap: datasetsDefaultLayerIds(datasets.basemap),
    };
  }, [datasets]);

  const getDefaultLayersForTab = useCallback(
    (tabName: string) => {
      switch (tabName) {
        case 'summary':
          return ['terrestrial', 'marine', 'basemap'].reduce(
            (slugs: string[], dataset) => [...slugs, ...defaultLayerSlugs[dataset]],
            []
          );
        case 'terrestrial':
          return defaultLayerSlugs.terrestrial;
        case 'marine':
          return defaultLayerSlugs.marine;
        default:
          return [];
      }
    },
    [defaultLayerSlugs]
  );

  const hasLoadedDatasets = datasets.terrestrial !== undefined || datasets.marine !== undefined;

  return { defaultLayerSlugs, getDefaultLayersForTab, hasLoadedDatasets };
}

// Sets the current tab's default layers on page load, if the URL has no layers
export default function useMapDefaultLayers() {
  const [mapLayers, setMapLayers] = useSyncMapLayers();
  const [{ tab }] = useSyncMapContentSettings();

  const { defaultLayerSlugs, getDefaultLayersForTab, hasLoadedDatasets } = useDefaultLayersForTab();

  const initialMapLayersRef = useRef(mapLayers);
  const hasSetInitialDefaultsRef = useRef(false);

  useEffect(() => {
    if (hasSetInitialDefaultsRef.current) return;
    if (!hasLoadedDatasets) return;

    hasSetInitialDefaultsRef.current = true;

    if (initialMapLayersRef.current.length > 0) return;

    setMapLayers(getDefaultLayersForTab(tab));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultLayerSlugs]);
}

// Returns a callback that switches the tab and sets that tab's default layers in one URL update
export function useChangeMapTab() {
  const [, setMapLayers] = useSyncMapLayers();
  const [{ tab: currentTab }, setSettings] = useSyncMapContentSettings();

  const { getDefaultLayersForTab } = useDefaultLayersForTab();

  return useCallback(
    (tab: string) => {
      if (tab === currentTab) return;

      setSettings((prevSettings) => ({ ...prevSettings, tab }));
      setMapLayers(getDefaultLayersForTab(tab));
    },
    [currentTab, setSettings, setMapLayers, getDefaultLayersForTab]
  );
}

const getTabFromQuery = (content: unknown): string => {
  try {
    return JSON.parse(content as string)?.tab ?? 'summary';
  } catch {
    return 'summary';
  }
};

// Returns a callback that sets the new page's default layers after navigation
export function useResetLayersOnNavigate() {
  const [, setMapLayers] = useSyncMapLayers();
  const { getDefaultLayersForTab } = useDefaultLayersForTab();

  const isResetPendingRef = useRef(false);
  const getDefaultLayersForTabRef = useRef(getDefaultLayersForTab);

  useEffect(() => {
    getDefaultLayersForTabRef.current = getDefaultLayersForTab;
  }, [getDefaultLayersForTab]);

  useEffect(() => {
    const onRouteChangeComplete = (_url: string, { shallow }: { shallow: boolean }) => {
      if (!isResetPendingRef.current || shallow) return;

      isResetPendingRef.current = false;
      setMapLayers(getDefaultLayersForTabRef.current(getTabFromQuery(Router.query.content)));
    };
    const onRouteChangeError = () => {
      isResetPendingRef.current = false;
    };

    Router.events.on('routeChangeComplete', onRouteChangeComplete);
    Router.events.on('routeChangeError', onRouteChangeError);
    return () => {
      Router.events.off('routeChangeComplete', onRouteChangeComplete);
      Router.events.off('routeChangeError', onRouteChangeError);
    };
  }, [setMapLayers]);

  return useCallback(() => {
    isResetPendingRef.current = true;
  }, []);
}
