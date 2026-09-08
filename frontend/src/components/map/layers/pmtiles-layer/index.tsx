import { useEffect, useMemo, useState } from 'react';

import { ClipExtension } from '@deck.gl/extensions/typed';
import { TileLayer, type TileLayerProps } from '@deck.gl/geo-layers/typed';
import type { TileLoadProps } from '@deck.gl/geo-layers/typed/tileset-2d/types';
import { BitmapLayer, GeoJsonLayer } from '@deck.gl/layers/typed';
import { PMTilesTileSource } from '@loaders.gl/pmtiles';
import GL from '@luma.gl/constants';
import type { Feature } from 'geojson';

import { useDeckMapboxOverlayContext } from '@/components/map/provider';
import { LayerProps } from '@/types/layers';

type RGBAColor = [number, number, number, number];

export interface PmtilesVectorRenderConfig {
  fillColor?: RGBAColor;
  lineColor?: RGBAColor;
  /** Line width in pixels */
  lineWidth?: number;
  /** Point radius in pixels */
  pointRadius?: number;
}

interface PmtilesLayerProps extends LayerProps {
  beforeId?: string;
  url: string;
  render?: PmtilesVectorRenderConfig;
  opacity?: number;
  visibility?: boolean;
}

type TileData = ImageBitmap | Feature[] | null;

// `beforeId` is honored by MapboxOverlay for layer ordering but isn't on
// deck.gl 8.9's typed TileLayerProps — extend locally rather than `as any`.
type PmtilesTileLayerProps = TileLayerProps<TileData> & { beforeId?: string };

const DEFAULT_MAX_ZOOM = 14;
const DEFAULT_FILL_COLOR: RGBAColor = [0, 100, 200, 120];
const DEFAULT_LINE_COLOR: RGBAColor = [0, 100, 200, 255];

const PmtilesLayer = ({
  id,
  beforeId,
  url,
  render,
  opacity = 1,
  visibility = true,
}: PmtilesLayerProps) => {
  const deckId = `${id}-deck`;
  const { addLayer, removeLayer } = useDeckMapboxOverlayContext();

  const [source, setSource] = useState<PMTilesTileSource | null>(null);
  const [archiveMaxZoom, setArchiveMaxZoom] = useState<number | undefined>();
  const [isVector, setIsVector] = useState(false);

  useEffect(() => {
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
        if (isVector) {
          const table = (await source.getVectorTile(index)) as { features: Feature[] } | null;
          return table?.features ?? null;
        }
        const data = await source.getTile(index);
        if (!data) return null;
        return createImageBitmap(new Blob([data], { type: 'image/png' }));
      },
      renderSubLayers: (props) => {
        const { content } = props.tile;
        if (!content) return null;
        const [[west, south], [east, north]] = props.tile.boundingBox;
        if (Array.isArray(content)) {
          // Clip to the tile bounds: MVT tiles carry a buffer, so unclipped
          // features would double-draw across tile seams.
          return new GeoJsonLayer<{ clipBounds: [number, number, number, number] }>({
            id: `${props.id}-geojson`,
            data: { type: 'FeatureCollection' as const, features: content },
            opacity: props.opacity,
            visible: props.visible,
            getFillColor: render?.fillColor ?? DEFAULT_FILL_COLOR,
            getLineColor: render?.lineColor ?? DEFAULT_LINE_COLOR,
            getLineWidth: render?.lineWidth ?? 1,
            lineWidthUnits: 'pixels',
            getPointRadius: render?.pointRadius ?? 3,
            pointRadiusUnits: 'pixels',
            extensions: [new ClipExtension()],
            clipBounds: [west, south, east, north],
          });
        }
        return new BitmapLayer({
          id: `${props.id}-bitmap`,
          image: content,
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
  }, [deckId, url, beforeId, source, archiveMaxZoom, isVector, render]);

  useEffect(() => {
    if (!layerProps) return;
    addLayer(
      new TileLayer<TileData>({
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
