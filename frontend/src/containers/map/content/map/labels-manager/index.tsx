import { useCallback, useEffect } from 'react';

import { useMap } from 'react-map-gl';

import { useLocale } from 'next-intl';

import { useSyncMapSettings } from '@/containers/map/content/map/sync-settings';

const LABELS_LAYER_ID = 'country-label';

const LabelsManager = () => {
  const { default: mapRef } = useMap();
  const [{ labels }] = useSyncMapSettings();
  const locale = useLocale();

  const toggleLabels = useCallback(() => {
    if (!mapRef) return;
    const map = mapRef.getMap();

    map.setLayoutProperty(LABELS_LAYER_ID, 'visibility', labels ? 'visible' : 'none');
    map.setLayoutProperty(LABELS_LAYER_ID, 'text-field', ['get', `name_${locale}`])
  }, [mapRef, labels, locale]);

  const handleStyleLoad = useCallback(() => {
    toggleLabels();
  }, [toggleLabels]);

  useEffect(() => {
    if (!mapRef) return;
    mapRef.on('style.load', handleStyleLoad);

    return () => {
      mapRef.off('style.load', handleStyleLoad);
    };
  }, [mapRef, handleStyleLoad]);

  useEffect(() => {
    if (!mapRef) return;
    toggleLabels();
  }, [mapRef, toggleLabels]);

  return null;
};

export default LabelsManager;
