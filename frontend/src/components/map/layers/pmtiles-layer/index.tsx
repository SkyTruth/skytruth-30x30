import { useEffect, useMemo, useState } from 'react';

import { TileLayer, type TileLayerProps } from '@deck.gl/geo-layers/typed';
import type { TileLoadProps } from '@deck.gl/geo-layers/typed/tileset-2d/types';
import { BitmapLayer } from '@deck.gl/layers/typed';
import { PMTilesTileSource } from '@loaders.gl/pmtiles';

import { useDeckMapboxOverlayContext } from '@/components/map/provider';
import { LayerProps } from '@/types/layers';

interface PmtilesLayerProps extends LayerProps {
  beforeId?: string;
  url: string;
  opacity?: number;
  visibility?: boolean;
}

type RasterTileData = ImageBitmap | null;

// `beforeId` is honored by MapboxOverlay for layer ordering but isn't on
// deck.gl 8.9's typed TileLayerProps — extend locally rather than `as any`.
type PmtilesTileLayerProps = TileLayerProps<RasterTileData> & { beforeId?: string };

const DEFAULT_MAX_ZOOM = 14;

const PmtilesLayer = ({ id, beforeId, url, opacity = 1, visibility = true }: PmtilesLayerProps) => {
  const deckId = `${id}-deck`;
  const { addLayer, removeLayer } = useDeckMapboxOverlayContext();

  const [source, setSource] = useState<PMTilesTileSource | null>(null);
  const [archiveMaxZoom, setArchiveMaxZoom] = useState<number | undefined>();

  useEffect(() => {
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

  const layerProps = useMemo<PmtilesTileLayerProps | null>(() => {
    if (!source) return null;
    return {
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
        });
      },
    };
  }, [deckId, url, beforeId, source, archiveMaxZoom]);

  useEffect(() => {
    if (!layerProps) return;
    addLayer(
      new TileLayer<RasterTileData>({
        ...layerProps,
        opacity,
        visible: visibility,
      })
    );
  }, [layerProps, opacity, visibility, addLayer]);

  useEffect(() => {
    return () => removeLayer(deckId);
  }, [deckId, removeLayer]);

  return null;
};

export default PmtilesLayer;
