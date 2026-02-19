import { useEffect, useRef } from 'react';

import { useAtom } from 'jotai';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import useCustomLayersIndexedDB from '@/hooks/use-custom-layers-indexed-db';
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
  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const { savedLayers, hasLoadedSavedLayers } = useCustomLayersIndexedDB();

  const allActiveLayersRef = useRef(allActiveLayers);

  useEffect(() => {
    allActiveLayersRef.current = allActiveLayers;
  }, [allActiveLayers]);

  // Add layers that have been saved to browser into state
  useEffect(() => {
    if (
      type !== MapTypes.ConservationBuilder ||
      !hasLoadedSavedLayers ||
      savedLayers.length === 0
    ) {
      return;
    }

    setCustomLayers((prev) => {
      const next = { ...prev };
      let hasChanges = false;

      savedLayers.forEach((layer) => {
        if (!next[layer.id]) {
          next[layer.id] = layer;
          hasChanges = true;
        }
      });

      return hasChanges ? next : prev;
    });
  }, [type, hasLoadedSavedLayers, savedLayers, setCustomLayers]);

  // keep allActiveLayers synchronized and stable in order while reacting to 
  // predefined/custom layer activation changes.
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
        (layer) => !preservedActiveLayers.includes(layer)
      );
      currentActiveLayers = [...newActiveLayers, ...preservedActiveLayers];
    }

    setAllActiveLayers(currentActiveLayers);
  }, [type, setAllActiveLayers, activeLayers, customLayers, allActiveLayersRef]);
};

export default useSyncAllLayers;
