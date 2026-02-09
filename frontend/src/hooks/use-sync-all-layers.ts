import { useEffect, useRef } from 'react';

import { useAtom } from 'jotai';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { MapTypes } from '@/types/map';

/**
 * This hook coordinates active layers between query params, state, and indexedDB. It also
 * picks up when the map swithces between progress tracker and conservation
 * builder and sets the allActiveLayers atom accordingly -> PT uses only predefined map layers
 * which are indicated in the query paramters, CB uses predefined layers and custom layers which
 * can be in the browsers indexedDB and/or in application state
 * @param type Which maptype is rendered - progress tracker or conservation builder
 *
 */
const useSyncAllLayers = (type: MapTypes) => {
  const [activeLayers] = useSyncMapLayers();

  const [allActiveLayers, setAllActiveLayers] = useAtom(allActiveLayersAtom);
  const [customLayers] = useAtom(customLayersAtom);

  const allActiveLayersRef = useRef(allActiveLayers);

  useEffect(() => {
    allActiveLayersRef.current = allActiveLayers;
  }, [allActiveLayers]);

  useEffect(() => {
    let currentActiveLayers = [...activeLayers];

    if (type === MapTypes.ConservationBuilder) {
      const activeCustomLayers = Object.keys(customLayers).filter(
        (layer) => customLayers[layer].isActive
      );

      const activeCustomLayersSet = new Set(activeCustomLayers);
      const activeLayersSet = new Set(activeLayers);

      const preservedActiveLayers = allActiveLayersRef.current.filter(
        (layer) => activeCustomLayersSet.has(layer) || activeLayersSet.has(layer)
      );

      const newActiveLayers = [...activeLayers, ...activeCustomLayers].filter(
        (key) => !preservedActiveLayers.includes(key)
      );
      currentActiveLayers = [...newActiveLayers, ...preservedActiveLayers];
    }

    setAllActiveLayers(currentActiveLayers);
  }, [type, setAllActiveLayers, activeLayers, customLayers, allActiveLayersRef]);
};

export default useSyncAllLayers;
