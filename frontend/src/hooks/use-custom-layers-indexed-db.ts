import { useCallback } from 'react';

import { useLiveQuery } from 'dexie-react-hooks';

import { indexedDB } from '@/lib/indexed-db';
import { CustomLayer } from '@/types/layers';

const useCustomLayersIndexedDB = () => {
  const isIndexedDBAvailable =
    typeof globalThis !== 'undefined' && typeof globalThis.indexedDB !== 'undefined';

  const savedLayers = useLiveQuery(async () => {
    if (!isIndexedDBAvailable) return [];

    return indexedDB.layers.toArray();
  }, [isIndexedDBAvailable]);

  const saveLayer = useCallback(
    async (layer: CustomLayer): Promise<void> => {
      if (!isIndexedDBAvailable) {
        throw new Error('IndexedDB is not available');
      }

      await indexedDB.layers.upsert(layer.id, layer);
    },
    [isIndexedDBAvailable]
  );

  const deleteLayer = useCallback(
    async (id: CustomLayer['id']): Promise<void> => {
      if (!isIndexedDBAvailable) {
        throw new Error('IndexedDB is not available');
      }

      await indexedDB.layers.delete(id);
    },
    [isIndexedDBAvailable]
  );

  return {
    savedLayers: savedLayers ?? [],
    hasLoadedSavedLayers: savedLayers !== undefined,
    isIndexedDBAvailable,
    saveLayer,
    deleteLayer,
  };
};

export default useCustomLayersIndexedDB;
