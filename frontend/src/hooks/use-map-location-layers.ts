import { useEffect, useRef } from 'react';

import { useRouter } from 'next/router';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { Location } from '@/types/generated/strapi.schemas';

// Slugs of the boundary layers for regions and countries, for each tab
const BOUNDARY_LAYER_SLUGS: Record<string, Record<'terrestrial' | 'marine', string[]>> = {
  region: { terrestrial: ['trr'], marine: ['mrr'] },
  country: { terrestrial: ['cnt'], marine: ['eez'] },
};

/**
 * When the user navigates to a country or region, turns on the boundary layers for that
 * location type and moves them to the top of the map. Only layers shown in the current tab
 * are considered, so the terrestrial tab gets terrestrial regions and the marine tab gets
 * marine regions.
 */
export default function useMapLocationLayers(location: Pick<Location, 'code' | 'type'>) {
  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const [, setMapLayers] = useSyncMapLayers();
  const [{ tab }] = useSyncMapContentSettings();

  // Keep track of location changes
  const previousLocationCodeRef = useRef(locationCode);
  const pendingLocationChangeRef = useRef(false);

  useEffect(() => {
    // Indicate that the user moved to a new location
    if (locationCode !== previousLocationCodeRef.current) {
      pendingLocationChangeRef.current = true;
    }
    previousLocationCodeRef.current = locationCode;

    // Wait until the new location's details have loaded
    if (!pendingLocationChangeRef.current || location?.code !== locationCode) return;
    pendingLocationChangeRef.current = false;

    // Get region/country layers, both land and ocean on the summary tab
    const layers = BOUNDARY_LAYER_SLUGS[location.type];
    if (!layers) return;

    const boundarySlugs =
      tab === 'summary' ? [...layers.terrestrial, ...layers.marine] : (layers[tab] ?? []);

    // Put the boundary layers first
    // If a boundary layer was already on, it's moved up
    setMapLayers((activeLayers) => [
      ...boundarySlugs,
      ...activeLayers.filter((slug) => !boundarySlugs.includes(slug)),
    ]);
  }, [locationCode, location, tab, setMapLayers]);
}
