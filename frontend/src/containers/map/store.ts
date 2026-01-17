import { MapLayerMouseEvent } from 'react-map-gl';

import { Feature } from 'geojson';
import { atom } from 'jotai';
import { atomWithReset } from 'jotai/utils';

import { CustomMapProps } from '@/components/map/types';
import type { SharedMarineAreaCountries } from '@/types';
import type { Layer } from '@/types/generated/strapi.schemas';
import type { CustomLayer } from '@/types/layers';
import { MapTypes } from '@/types/map';
import type { ModellingData } from '@/types/modelling';

export const sidebarAtom = atom(true);
export const layersAtom = atom(false);

// ? Map state
export const mapTypeAtom = atom<MapTypes>(MapTypes.ProgressTracker);
export const layersInteractiveAtom = atom<Layer['slug'][]>([]);
export const layersInteractiveIdsAtom = atom<string[]>([]);
export const bboxLocationAtom = atomWithReset<CustomMapProps['bounds']['bbox']>([
  -180, -85.5624999997749, 180, 90,
]);
export const popupAtom = atom<Partial<MapLayerMouseEvent | null>>({});
export const drawStateAtom = atomWithReset<{
  active: boolean;
  status: 'idle' | 'drawing' | 'success';
  feature: Feature;
}>({
  active: false,
  status: 'idle',
  feature: null,
});
export const allActiveLayersAtom = atom<Array<string>>([]);
export const customLayersAtom = atom<{ [key: string]: CustomLayer }>({});

export const sharedMarineAreaCountriesAtom = atom<SharedMarineAreaCountries>([]);

// ? modelling state
export const modellingAtom = atomWithReset<{
  active: boolean;
  status: 'idle' | 'running' | 'success' | 'error';
  data: ModellingData;
  errorMessage?: string;
}>({
  active: false,
  status: 'idle',
  data: null,
  errorMessage: undefined,
});
