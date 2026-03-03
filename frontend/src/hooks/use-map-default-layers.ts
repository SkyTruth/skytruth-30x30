import { useCallback, useEffect, useMemo, useRef } from 'react';

import { usePreviousImmediate } from 'rooks';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';

import useDatasetsByEnvironment from './use-datasets-by-environment';

export default function useMapDefaultLayers() {
  const [mapLayers, setMapLayers] = useSyncMapLayers();
  const [{ tab }] = useSyncMapContentSettings();

  const previousTab = usePreviousImmediate(tab);

  const [datasets] = useDatasetsByEnvironment();

  // Capture the URL's layer state at mount time, before any async data arrives.
  // nuqs reads the URL synchronously on first render, so this ref reflects what
  // was actually in the URL when the user landed on the page.
  const initialMapLayersRef = useRef(mapLayers);

  // Ensures Effect 1 (initial defaults) only fires once per mount, and gates
  // Effect 2 (tab changes) so it doesn't fire for the forced summary→terrestrial
  // switch that happens before datasets have loaded.
  const hasSetInitialDefaultsRef = useRef(false);

  const defaultLayerSlugs = useMemo(() => {
    const datasetsDefaultLayerIds = (datasets = []) => {
      return datasets.reduce((acc, { attributes }) => {
        const layersData = attributes?.layers?.data;

        const defaultLayerSlugs = layersData.reduce(
          (acc, { attributes }) => (attributes?.default ? [...acc, attributes.slug] : acc),
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

  // Initial page load set for default map layers. Only fires if the layers query param is
  // empty or missing
  useEffect(() => {
    if (hasSetInitialDefaultsRef.current) return;
    if (datasets.terrestrial === undefined && datasets.marine === undefined) {
      return; // datasets not yet loaded
    }

    hasSetInitialDefaultsRef.current = true;

    if (initialMapLayersRef.current.length > 0) {
      // URL already had layers when the page loaded — respect the user's state.
      return;
    }

    setMapLayers(getDefaultLayersForTab(tab));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultLayerSlugs]);
  // Intentionally excludes `tab` since this is to catch only the initial map load
  // and Conservation builder forces tab to a new state often while data is fetching

  // Sets default map layers on tab switch, only runs after above initial set-up has run
  useEffect(() => {
    if (!hasSetInitialDefaultsRef.current) return;

    if (tab !== previousTab && !!previousTab) {
      const mapLayers = getDefaultLayersForTab(tab);
      setMapLayers(mapLayers);
    }
  }, [tab, previousTab, defaultLayerSlugs, setMapLayers, getDefaultLayersForTab]);
}
