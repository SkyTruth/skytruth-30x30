import { useEffect, useRef } from 'react';

import { useAtom } from 'jotai';

import { useSyncMapLayers } from '@/containers/map/content/map/sync-settings';
import { allActiveLayersAtom, customLayersAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import useCustomLayersIndexedDB from '@/hooks/use-custom-layers-indexed-db';
import { MapTypes } from '@/types/map';

/**
 * This hook coordinates active layers between query params, state, and indexedDB.
 * It also picks up when the map switches between Progress Tracker (PT)
 * and Conservation Builder (CB) and sets the allActiveLayers atom accordingly.
 * - PT uses only predefined map layers which are indicated in the query parameters.
 * - CB uses predefined layers and custom layers which can be in the browser's
 *   indexedDB and/or in application state.
 * On environment switch (tab change), a ref-based signal ensures custom layers stay
 * at the top of the legend order.
 * @param type Which map type is rendered: Progress Tracker or Conservation Builder
 */
const useSyncAllLayers = (type: MapTypes) => {
  const [activeLayers] = useSyncMapLayers();

  const [allActiveLayers, setAllActiveLayers] = useAtom(allActiveLayersAtom);
  const [customLayers, setCustomLayers] = useAtom(customLayersAtom);
  const { savedLayers, hasLoadedSavedLayers } = useCustomLayersIndexedDB();
  const [{ tab }] = useSyncMapContentSettings();

  const allActiveLayersRef = useRef(allActiveLayers);
  const environmentSwitchedRef = useRef(false);
  const previousTabRef = useRef(tab);

  useEffect(() => {
    allActiveLayersRef.current = allActiveLayers;
  }, [allActiveLayers]);

  // Track when the environment (tab) changes
  useEffect(() => {
    if (previousTabRef.current !== tab) {
      environmentSwitchedRef.current = true;
      previousTabRef.current = tab;
    }
  }, [tab]);

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

  // Keep allActiveLayers synchronized whenever the active layer set
  // (custom or predefined) changes. Newly-added layers appear at the
  // top of the legend. When switching environments, custom layers are
  // always first followed by predefined layers.
  useEffect(() => {
    if (type === MapTypes.ProgressTracker) {
      setAllActiveLayers([...activeLayers]);
    } else if (type === MapTypes.ConservationBuilder) {
      const activeCustomLayers = Object.keys(customLayers).filter(
        (layer) => customLayers[layer].isActive
      );

      const allTargetLayers = new Set([...activeCustomLayers, ...activeLayers]);

      // Skip if only the order changed (no new layers)
      if (
        allActiveLayersRef.current.length === allTargetLayers.size &&
        allActiveLayersRef.current.every((l) => allTargetLayers.has(l))
      )
        return;

      // Layers still active from the previous order
      const preservedLayers = allActiveLayersRef.current.filter((layer) =>
        allTargetLayers.has(layer)
      );
      const preservedLayersSet = new Set(preservedLayers);

      // Layers newly active
      const newLayers = [...allTargetLayers].filter((layer) => !preservedLayersSet.has(layer));

      // If the environment has switched, custom layers move to the top
      if (environmentSwitchedRef.current) {
        environmentSwitchedRef.current = false;
        setAllActiveLayers([...preservedLayers, ...newLayers]);
      } else {
        setAllActiveLayers([...newLayers, ...preservedLayers]);
      }
    }
  }, [type, setAllActiveLayers, activeLayers, customLayers, allActiveLayersRef]);
};

export default useSyncAllLayers;
