import { useEffect, useState } from 'react';

import { TileLayer, type TileLayerProps } from '@deck.gl/geo-layers/typed';
import type { TileLoadProps } from '@deck.gl/geo-layers/typed/tileset-2d/types';
import { BitmapLayer } from '@deck.gl/layers/typed';
import { PMTilesTileSource } from '@loaders.gl/pmtiles';
import GL from '@luma.gl/constants';

import { useDeckMapboxOverlayContext } from '@/components/map/provider';
import { LayerProps } from '@/types/layers';

import PmtilesMvtLayer from './pmtiles-mvt-layer';

type RGBAColor = [number, number, number, number];

export interface PmtilesVectorRenderConfig {
  fillColor?: RGBAColor;
  lineColor?: RGBAColor;
  /** Line width in pixels */
  lineWidth?: number;
  /** Point radius in pixels */
  pointRadius?: number;
  /**
   * Property identifying a feature across tiles, like Mapbox's `promoteId`.
   * Set it on every vector layer so hover highlights whole features.
   */
  uniqueIdProperty?: string;
  highlightColor?: RGBAColor;
}

interface PmtilesLayerProps extends LayerProps {
  beforeId?: string;
  url: string;
  render?: PmtilesVectorRenderConfig;
  opacity?: number;
  visibility?: boolean;
}

type RasterTileData = ImageBitmap | null;

// `beforeId` is honored by MapboxOverlay for layer ordering but isn't on
// deck.gl 8.9's typed TileLayerProps — extend locally rather than `as any`.
type RasterTileLayerProps = TileLayerProps<RasterTileData> & { beforeId?: string };

const DEFAULT_MAX_ZOOM = 14;
const DEFAULT_FILL_COLOR: RGBAColor = [0, 100, 200, 120];
const DEFAULT_LINE_COLOR: RGBAColor = [0, 100, 200, 255];
const DEFAULT_HIGHLIGHT_COLOR: RGBAColor = [253, 142, 40, 160];

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

  useEffect(() => {
    if (!source) return;

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
          getFillColor: render?.fillColor ?? DEFAULT_FILL_COLOR,
          getLineColor: render?.lineColor ?? DEFAULT_LINE_COLOR,
          getLineWidth: render?.lineWidth ?? 1,
          lineWidthUnits: 'pixels',
          getPointRadius: render?.pointRadius ?? 3,
          pointRadiusUnits: 'pixels',
          pickable: true,
          autoHighlight: true,
          highlightColor: render?.highlightColor ?? DEFAULT_HIGHLIGHT_COLOR,
          uniqueIdProperty: render?.uniqueIdProperty,
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
    render,
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
