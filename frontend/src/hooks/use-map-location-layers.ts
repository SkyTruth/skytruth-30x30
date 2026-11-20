import { useEffect, useRef } from 'react';

import { useRouter } from 'next/router';

import { EEZ_SOURCE } from '@/containers/map/content/map/popup/constants';
import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { Location } from '@/types/generated/strapi.schemas';

import useDatasetsByEnvironment from './use-datasets-by-environment';

// Identify layers for regions and countries
const BOUNDARY_SOURCES_BY_LOCATION_TYPE: Record<string, string[]> = {
  region: ['terrestrial-regions', 'marine-regions-source'],
  country: ['countries', EEZ_SOURCE],
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
  const [datasets] = useDatasetsByEnvironment();

  // Keep track of location changes
  const previousLocationCodeRef = useRef(locationCode);
  const pendingLocationChangeRef = useRef(false);

  useEffect(() => {
    // Indicate that the user moved to a new location
    if (locationCode !== previousLocationCodeRef.current) {
      pendingLocationChangeRef.current = true;
    }
    previousLocationCodeRef.current = locationCode;

    // Wait until the new location's details and the list of map layers have loaded
    const isDataReady = location?.code === locationCode && datasets.terrestrial !== undefined;
    if (!pendingLocationChangeRef.current || !isDataReady) return;
    pendingLocationChangeRef.current = false;

    // Get region/country layers
    const sources = BOUNDARY_SOURCES_BY_LOCATION_TYPE[location.type];
    if (!sources) return;

    const environments =
      tab === 'summary' ? [datasets.terrestrial, datasets.marine] : [datasets[tab]];

    const boundarySlugs = environments
      .flat()
      .flatMap((dataset) => dataset?.layers ?? [])
      .filter((layer) =>
        sources.includes((layer?.config as { source?: { id?: string } })?.source?.id)
      )
      .map(({ slug }) => slug);

    // Put the boundary layers first
    // If a boundary layer was already on, it's moved up
    setMapLayers((activeLayers) => [
      ...boundarySlugs,
      ...activeLayers.filter((slug) => !boundarySlugs.includes(slug)),
    ]);
  }, [locationCode, location, datasets, tab, setMapLayers]);
}
