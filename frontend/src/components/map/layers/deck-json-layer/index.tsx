import { useEffect } from 'react';

import { useDeckMapboxOverlayContext } from '@/components/map/provider';
import { LayerProps } from '@/types/layers';

export type DeckJsonLayerProps<T> = LayerProps &
  Partial<T> & {
    beforeId: string;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    config: any;
  };

const DeckJsonLayer = <T,>({ id, beforeId, config }: DeckJsonLayerProps<T>) => {
  // Render deck config
  const deckId = `${id}-deck`;
  const { addLayer, removeLayer } = useDeckMapboxOverlayContext();

  useEffect(() => {
    addLayer(config.clone({ id: deckId, beforeId }));
  }, [deckId, beforeId, config, addLayer]);

  useEffect(() => {
    return () => {
      removeLayer(deckId);
    };
  }, [deckId, removeLayer]);

  return null;
};

export default DeckJsonLayer;
