import { Dexie, type EntityTable } from 'dexie';

import { CustomLayer } from '@/types/layers';

type CustomLayersDB = Dexie & {
  layers: EntityTable<CustomLayer, 'id'>;
};

export const indexedDB = new Dexie('CustomLayersDB') as CustomLayersDB;

indexedDB.version(1).stores({
  layers: '&id',
});

export const saveCustomLayer = async (layer: CustomLayer): Promise<void> => {
  if (typeof window === 'undefined') return;

  await indexedDB.layers.put(layer);
};
