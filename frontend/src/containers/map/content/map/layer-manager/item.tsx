import { useCallback, useMemo } from 'react';

import { useParams } from 'next/navigation';

import { useAtom } from 'jotai';
import { useLocale } from 'next-intl';

import DeckJsonLayer from '@/components/map/layers/deck-json-layer';
import MapboxLayer from '@/components/map/layers/mapbox-layer';
import { layersInteractiveAtom, layersInteractiveIdsAtom } from '@/containers/map/store';
import useResolvedConfig from '@/hooks/use-resolved-config';
import { useGetLayers } from '@/types/generated/layer';
import { Layer } from '@/types/generated/strapi.schemas';
import { Config, LayerTyped } from '@/types/layers';

interface LayerManagerItemProps extends Required<Pick<Layer, 'slug'>> {
  beforeId: string;
  settings: Record<string, unknown>;
}

const LayerManagerItem = ({ slug, beforeId, settings }: LayerManagerItemProps) => {
  const locale = useLocale();

  const { data: layer } = useGetLayers(
    {
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
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

  const { type, config, params_config } = (layer as LayerTyped) ?? ({} as LayerTyped);

  const configParams = useMemo(
    () => ({
      config,
      params_config,
      settings: {
        ...settings,
        location: locationCode,
      },
    }),
    [config, locationCode, params_config, settings]
  );

  const parsedConfig = useResolvedConfig(configParams);

  const handleAddMapboxLayer = useCallback(
    ({ styles }: Config) => {
      if (layer) return null;

      const { interaction_config } = layer as LayerTyped;

      if (interaction_config?.enabled) {
        const ids = styles.map((l) => l.id);

        setLayersInteractive((prev) => Array.from(new Set([...prev, slug])));
        setLayersInteractiveIds((prev) => Array.from(new Set([...prev, ...ids])));
      }
    },
    [layer, slug, setLayersInteractive, setLayersInteractiveIds]
  );

  const handleRemoveMapboxLayer = useCallback(
    ({ styles }: Config) => {
      if (layer) return null;

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
