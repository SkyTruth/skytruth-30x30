import { useEffect, useRef } from 'react';

import { useAtom } from 'jotai';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { MapTypes } from '@/types/map';

/**
 *  This hooks picks up when the map swithces between progress tracker and conservation
 * builder and sets the allActiveLayers atom accordingly -> PT uses only prediofned map layers
 * which are indicated in the query paramters, CB uses predefined layers and custom layers which
 * are can be in the browsers indexedDB and/or in application state
 * @param type Which maptype is rendered - progress tracker or conservation builder
 *
 */
const useSyncAllLayers = (type: MapTypes) => {
  const [activeLayers] = useSyncMapLayers();

  const [, setAllActiveLayers] = useAtom(allActiveLayersAtom);
  const [customLayers] = useAtom(customLayersAtom);

  const activeLayersRef = useRef(activeLayers);
  const customLayersRef = useRef(customLayers);

  useEffect(() => {
    activeLayersRef.current = activeLayers;
  }, [activeLayers]);
  useEffect(() => {
    customLayersRef.current = customLayers;
  }, [customLayers]);

  useEffect(() => {
    const activeLayers = activeLayersRef.current;
    const customLayers = customLayersRef.current;

    let currentActiveLayers = activeLayers;

    if (type === MapTypes.ConservationBuilder) {
      const activeCustomLayers = Object.keys(customLayers).filter((k) => customLayers[k].isActive);

      currentActiveLayers = [...activeCustomLayers, ...activeLayers];
    }

    setAllActiveLayers(currentActiveLayers);
  }, [type, setAllActiveLayers]);
};

export default useSyncAllLayers;
