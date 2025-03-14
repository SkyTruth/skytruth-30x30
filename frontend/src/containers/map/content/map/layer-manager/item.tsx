import { useCallback, useMemo } from 'react';

import { useParams } from 'next/navigation';

import { useAtom } from 'jotai';
import { useLocale } from 'next-intl';

import DeckJsonLayer from '@/components/map/layers/deck-json-layer';
import MapboxLayer from '@/components/map/layers/mapbox-layer';
import { layersInteractiveAtom, layersInteractiveIdsAtom } from '@/containers/map/store';
import useResolvedConfig from '@/hooks/use-resolved-config';
import { useGetLayersId } from '@/types/generated/layer';
import { LayerResponseDataObject } from '@/types/generated/strapi.schemas';
import { Config, LayerTyped } from '@/types/layers';

interface LayerManagerItemProps extends Required<Pick<LayerResponseDataObject, 'id'>> {
  beforeId: string;
  settings: Record<string, unknown>;
}

const LayerManagerItem = ({ id, beforeId, settings }: LayerManagerItemProps) => {
  const locale = useLocale();

  const { data } = useGetLayersId(id, {
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    locale,
    populate: 'metadata',
  });
  const [, setLayersInteractive] = useAtom(layersInteractiveAtom);
  const [, setLayersInteractiveIds] = useAtom(layersInteractiveIdsAtom);
  const { locationCode = 'GLOB' } = useParams();

  const { type, config, params_config } =
    (data?.data?.attributes as LayerTyped) ?? ({} as LayerTyped);

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
      if (!data?.data?.attributes) return null;

      const { interaction_config } = data.data.attributes as LayerTyped;

      if (interaction_config?.enabled) {
        const ids = styles.map((l) => l.id);

        setLayersInteractive((prev) => Array.from(new Set([...prev, id])));
        setLayersInteractiveIds((prev) => Array.from(new Set([...prev, ...ids])));
      }
    },
    [data?.data?.attributes, id, setLayersInteractive, setLayersInteractiveIds]
  );

  const handleRemoveMapboxLayer = useCallback(
    ({ styles }: Config) => {
      if (!data?.data?.attributes) return null;

      const { interaction_config } = data.data.attributes as LayerTyped;

      if (interaction_config?.enabled) {
        const ids = styles.map((l) => l.id);

        setLayersInteractive((prev) => prev.filter((i) => i !== id));
        setLayersInteractiveIds((prev) => prev.filter((i) => !ids.includes(i)));
      }
    },
    [data?.data?.attributes, id, setLayersInteractive, setLayersInteractiveIds]
  );

  if (!parsedConfig) {
    return null;
  }

  if (type === 'mapbox') {
    return (
      <MapboxLayer
        id={`${id}-layer`}
        beforeId={beforeId}
        config={parsedConfig as Config}
        onAdd={handleAddMapboxLayer}
        onRemove={handleRemoveMapboxLayer}
      />
    );
  }

  if (type === 'deckgl') {
    return <DeckJsonLayer id={`${id}-layer`} beforeId={beforeId} config={parsedConfig} />;
  }

  return null;
};

export default LayerManagerItem;
