import { useEffect, useState } from 'react';

import {
  TileLayer,
  type TileLayerProps,
  type _TileLoadProps as TileLoadProps,
} from '@deck.gl/geo-layers';
import { BitmapLayer } from '@deck.gl/layers';
import { PMTilesTileSource } from '@loaders.gl/pmtiles';

import { useDeckMapboxOverlayContext } from '@/components/map/provider';
import { Config, LayerProps } from '@/types/layers';

interface PmtilesLayerProps extends LayerProps {
  beforeId?: string;
  config: Config;
  opacity?: number;
  visibility?: boolean;
}

type TileData = ImageBitmap | null;

// `beforeId` is honored by MapboxOverlay for layer ordering but isn't on
// deck.gl's typed TileLayerProps — extend locally rather than `as any`.
type PmtilesTileLayerProps = TileLayerProps<TileData> & { beforeId?: string };

const DEFAULT_MAX_ZOOM = 14;

const PmtilesLayer = ({
  id,
  beforeId,
  config,
  opacity = 1,
  visibility = true,
}: PmtilesLayerProps) => {
  const deckId = `${id}-deck`;
  const { addLayer, removeLayer } = useDeckMapboxOverlayContext();
  const url = 'url' in config.source ? config.source.url : undefined;

  const [source, setSource] = useState<PMTilesTileSource | null>(null);
  const [archiveMaxZoom, setArchiveMaxZoom] = useState<number | undefined>();

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    const next = new PMTilesTileSource(url, { pmtiles: {} });
    next
      .getMetadata()
      .then((meta) => {
        if (cancelled) return;
        setSource(next);
        setArchiveMaxZoom(meta.maxZoom);
      })
      .catch(() => {
        if (cancelled) return;
        setSource(next);
      });
    return () => {
      cancelled = true;
      setSource(null);
      setArchiveMaxZoom(undefined);
    };
  }, [url]);

  useEffect(() => {
    if (!source || !url) return;

    const layerProps: PmtilesTileLayerProps = {
      id: deckId,
      // `data` is required by TileLayerProps but unused when getTileData is set;
      // pass the archive URL so the type is satisfied and tile cache keying stays
      // tied to the source.
      data: url,
      beforeId,
      tileSize: 256,
      minZoom: 0,
      maxZoom: archiveMaxZoom ?? DEFAULT_MAX_ZOOM,
      refinementStrategy: 'best-available',
      maxRequests: 6,
      opacity,
      visible: visibility,
      getTileData: async ({ index }: TileLoadProps) => {
        const data = await source.getTile(index);
        if (!data) return null;
        return createImageBitmap(new Blob([data], { type: 'image/png' }));
      },
      renderSubLayers: (props) => {
        if (!props.tile.content) return null;
        const [[west, south], [east, north]] = props.tile.boundingBox;
        return new BitmapLayer({
          id: `${props.id}-bitmap`,
          image: props.tile.content,
          bounds: [west, south, east, north],
          opacity: props.opacity,
          visible: props.visible,
          textureParameters: { minFilter: 'nearest', magFilter: 'nearest' },
        });
      },
    };
    addLayer(new TileLayer<TileData>(layerProps));
  }, [deckId, url, beforeId, source, archiveMaxZoom, opacity, visibility, addLayer]);

  useEffect(() => {
    return () => removeLayer(deckId);
  }, [deckId, removeLayer]);

  return null;
};

export default PmtilesLayer;
