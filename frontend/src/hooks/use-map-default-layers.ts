import { useEffect, useMemo } from 'react';

import { usePreviousImmediate } from 'rooks';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';

import useDatasetsByEnvironment from './use-datasets-by-environment';

export default function useMapDefaultLayers() {
  const [, setMapLayers] = useSyncMapLayers();
  const [{ tab }] = useSyncMapContentSettings();
  const previousTab = usePreviousImmediate(tab);

  const [datasets] = useDatasetsByEnvironment();

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

  useEffect(() => {
    if (tab !== previousTab && !!previousTab) {
      let mapLayers = [];
      switch (tab) {
        case 'summary':
          mapLayers = ['terrestrial', 'marine', 'basemap']?.reduce(
            (slugs, dataset) => [...slugs, ...defaultLayerSlugs[dataset]],
            []
          );
          break;
        case 'terrestrial':
          mapLayers = defaultLayerSlugs.terrestrial;
          break;
        case 'marine':
          mapLayers = defaultLayerSlugs.marine;
          break;
      }
      setMapLayers(mapLayers);
    }
  }, [defaultLayerSlugs, setMapLayers, tab, previousTab]);
}
