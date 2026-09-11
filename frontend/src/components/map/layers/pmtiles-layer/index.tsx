import { useEffect, useMemo, useState } from 'react';

import { TileLayer, type TileLayerProps } from '@deck.gl/geo-layers/typed';
import type { TileLoadProps } from '@deck.gl/geo-layers/typed/tileset-2d/types';
import { BitmapLayer } from '@deck.gl/layers/typed';
import { PMTilesTileSource } from '@loaders.gl/pmtiles';
import GL from '@luma.gl/constants';

import { useDeckMapboxOverlayContext } from '@/components/map/provider';
import { Config, LayerProps } from '@/types/layers';

import PmtilesMvtLayer from './pmtiles-mvt-layer';
import { compileStyles, type RGBAColor } from './style-interpreter';

interface PmtilesLayerProps extends LayerProps {
  beforeId?: string;
  config: Config;
  opacity?: number;
  visibility?: boolean;
}

type RasterTileData = ImageBitmap | null;

// `beforeId` is honored by MapboxOverlay for layer ordering but isn't on
// deck.gl 8.9's typed TileLayerProps — extend locally rather than `as any`.
type RasterTileLayerProps = TileLayerProps<RasterTileData> & { beforeId?: string };

const DEFAULT_MAX_ZOOM = 14;
const DEFAULT_HIGHLIGHT_COLOR: RGBAColor = [253, 142, 40, 160];

const PmtilesLayer = ({
  id,
  beforeId,
  config,
  opacity = 1,
  visibility = true,
}: PmtilesLayerProps) => {
  const deckId = `${id}-deck`;
  const { addLayer, removeLayer } = useDeckMapboxOverlayContext();

  const { source: sourceConfig } = config;
  const url = 'url' in sourceConfig ? sourceConfig.url : undefined;
  const uniqueIdProperty =
    'promoteId' in sourceConfig && typeof sourceConfig.promoteId === 'string'
      ? sourceConfig.promoteId
      : undefined;
  const styles = useMemo(() => compileStyles(config.styles), [config.styles]);

  const [source, setSource] = useState<PMTilesTileSource | null>(null);
  const [archiveMaxZoom, setArchiveMaxZoom] = useState<number | undefined>();
  const [isVector, setIsVector] = useState(false);

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
        setIsVector(meta.tileMIMEType === 'application/vnd.mapbox-vector-tile');
      })
      .catch(() => {
        if (cancelled) return;
        setSource(next);
      });
    return () => {
      cancelled = true;
      setSource(null);
      setArchiveMaxZoom(undefined);
      setIsVector(false);
    };
  }, [url]);

  useEffect(() => {
    if (!source || !url) return;

    const common = {
      id: deckId,
      beforeId,
      minZoom: 0,
      maxZoom: archiveMaxZoom ?? DEFAULT_MAX_ZOOM,
      refinementStrategy: 'best-available' as const,
      maxRequests: 6,
      opacity,
      visible: visibility,
    };

    if (isVector) {
      addLayer(
        new PmtilesMvtLayer({
          ...common,
          source,
          styles,
          pickable: true,
          autoHighlight: true,
          highlightColor: DEFAULT_HIGHLIGHT_COLOR,
          uniqueIdProperty,
        })
      );
      return;
    }

    const rasterProps: RasterTileLayerProps = {
      ...common,
      // `data` is required by TileLayerProps but unused when getTileData is set;
      // pass the archive URL so the type is satisfied and tile cache keying stays
      // tied to the source.
      data: url,
      tileSize: 256,
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
          textureParameters: {
            [GL.TEXTURE_MIN_FILTER]: GL.NEAREST,
            [GL.TEXTURE_MAG_FILTER]: GL.NEAREST,
          },
        });
      },
    };
    addLayer(new TileLayer<RasterTileData>(rasterProps));
  }, [
    deckId,
    url,
    beforeId,
    source,
    archiveMaxZoom,
    isVector,
    uniqueIdProperty,
    styles,
    opacity,
    visibility,
    addLayer,
  ]);

  useEffect(() => {
    return () => removeLayer(deckId);
  }, [deckId, removeLayer]);

  return null;
};

export default PmtilesLayer;
