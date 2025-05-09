import { parseAsArrayOf, parseAsString, parseAsJson, useQueryState } from 'nuqs';
import { z } from 'zod';

import {
  contentSettingsSchema,
  ContentSettings,
  useSyncMapContentSettings,
} from '@/containers/map/sync-settings';
import { LayerSettings, layerSettingsSchema } from '@/types/layers';

const mapSettingsSchema = z.object({
  bbox: z.array(z.number()).optional(),
  labels: z.boolean().optional(),
});

type MapSettings = z.infer<typeof mapSettingsSchema>;

const DEFAULT_SYNC_MAP_SETTINGS: MapSettings = {
  bbox: null,
  labels: true,
};

export const useSyncMapSettings = () => {
  return useQueryState(
    'settings',
    parseAsJson<MapSettings>(mapSettingsSchema.parse).withDefault(DEFAULT_SYNC_MAP_SETTINGS)
  );
};

export const useSyncMapLayers = () => {
  return useQueryState('layers', parseAsArrayOf(parseAsString).withDefault([]));
};

export const useSyncMapLayerSettings = () => {
  return useQueryState(
    'layer-settings',
    parseAsJson<LayerSettings>(layerSettingsSchema.parse).withDefault({})
  );
};

// ? there is an issue where NextJS's useSearchParams will not return the update searchParams
// ? updated via next-usequerystate, so we rely in next-usequerystate to retrieve those searchParams as well
// ? this might be an issue with next-usequerystate, but for now we can make it work this way.
// ! if you are using syncing a new state through next-usequerystate in the data-tool's map page, remember to register it here
export const useMapSearchParams = (): URLSearchParams => {
  const [settings] = useSyncMapSettings();
  const [layers] = useSyncMapLayers();
  const [layerSettings] = useSyncMapLayerSettings();
  const [contentSettings] = useSyncMapContentSettings();
  const currentSearchparams = new URLSearchParams();

  currentSearchparams.set('layers', parseAsArrayOf(parseAsString).serialize(layers));
  currentSearchparams.set(
    'settings',
    parseAsJson<MapSettings>(mapSettingsSchema.parse).serialize(settings)
  );
  currentSearchparams.set(
    'layer-settings',
    parseAsJson<LayerSettings>(layerSettingsSchema.parse).serialize(layerSettings)
  );
  currentSearchparams.set(
    'content',
    parseAsJson<ContentSettings>(contentSettingsSchema.parse).serialize(contentSettings)
  );

  return currentSearchparams;
};
