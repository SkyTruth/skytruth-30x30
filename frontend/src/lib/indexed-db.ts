import { Dexie, type EntityTable } from 'dexie';

import { CustomLayer } from '@/types/layers';

type CustomLayersDB = Dexie & {
  layers: EntityTable<CustomLayer, 'id'>;
};

export const indexedDB = new Dexie('CustomLayersDB') as CustomLayersDB;

indexedDB.version(1).stores({
  layers: '&id',
});
