import { useCallback, useMemo } from 'react';

import { useParams } from 'next/navigation';

import { useAtom } from 'jotai';
import { useLocale } from 'next-intl';

import DeckJsonLayer from '@/components/map/layers/deck-json-layer';
import MapboxLayer from '@/components/map/layers/mapbox-layer';
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { layersInteractiveAtom, layersInteractiveIdsAtom } from '@/containers/map/store';
import useResolvedConfig from '@/hooks/use-resolved-config';
import { useGetLayers } from '@/types/generated/layer';
import { Layer } from '@/types/generated/strapi.schemas';
import { Config, LayerTyped } from '@/types/layers';

import { useSyncCustomRegion } from '../sync-settings';

interface LayerManagerItemProps extends Required<Pick<Layer, 'slug'>> {
  beforeId: string;
  settings: Record<string, unknown>;
}

const LayerManagerItem = ({ slug, beforeId, settings }: LayerManagerItemProps) => {
  const locale = useLocale();

  const { data: layer } = useGetLayers(
    {
      // @ts-ignore
      filters: {
        slug: {
          $eq: slug,
        },
      },
      sort: 'interaction_config',
      locale,
      populate: 'metadata',
    },
    {
      query: {
        select: ({ data }) => data[0]?.attributes,
      },
    }
  );

  const [, setLayersInteractive] = useAtom(layersInteractiveAtom);
  const [, setLayersInteractiveIds] = useAtom(layersInteractiveIdsAtom);
  const { locationCode = 'GLOB' } = useParams();
  const [customRegionLocations] = useSyncCustomRegion();

  const isCustomRegionActive = locationCode === CUSTOM_REGION_CODE;

  const customRegionMap = useMemo(() => {
    const map = {};
    for (const loc of customRegionLocations) {
      map[loc] = true;
    }
    return map;
  }, [customRegionLocations]);

  const { type, config, params_config } = (layer as LayerTyped) ?? ({} as LayerTyped);

  const configParams = useMemo(
    () => ({
      config,
      params_config,
      settings: {
        ...settings,
        location: locationCode,
        customRegionLocations: isCustomRegionActive ? customRegionMap : {},
      },
    }),
    [config, locationCode, params_config, settings, customRegionMap, isCustomRegionActive]
  );

  const parsedConfig = useResolvedConfig(configParams);

  const handleAddMapboxLayer = useCallback(
    ({ styles }: Config) => {
      const { interaction_config } = layer as LayerTyped;

      if (interaction_config?.enabled) {
        const ids = styles.map((l) => l.id);

        setLayersInteractive((prev) => {
          return Array.from(new Set([...prev, slug]));
        });
        setLayersInteractiveIds((prev) => Array.from(new Set([...prev, ...ids])));
      }
    },
    [layer, slug, setLayersInteractive, setLayersInteractiveIds]
  );

  const handleRemoveMapboxLayer = useCallback(
    ({ styles }: Config) => {
      const { interaction_config } = layer as LayerTyped;

      if (interaction_config?.enabled) {
        const ids = styles.map((l) => l.id);

        setLayersInteractive((prev) => prev.filter((i) => i !== slug));
        setLayersInteractiveIds((prev) => prev.filter((i) => !ids.includes(i)));
      }
    },
    [layer, slug, setLayersInteractive, setLayersInteractiveIds]
  );

  if (!parsedConfig) {
    return null;
  }

  if (type === 'mapbox') {
    return (
      <MapboxLayer
        id={`${slug}-layer`}
        beforeId={beforeId}
        config={parsedConfig as Config}
        onAdd={handleAddMapboxLayer}
        onRemove={handleRemoveMapboxLayer}
      />
    );
  }

  if (type === 'deckgl') {
    return <DeckJsonLayer id={`${slug}-layer`} beforeId={beforeId} config={parsedConfig} />;
  }

  return null;
};

export default LayerManagerItem;
