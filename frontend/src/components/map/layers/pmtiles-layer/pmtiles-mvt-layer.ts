import { MVTLayer } from '@deck.gl/geo-layers/typed';
import type { TileLoadProps } from '@deck.gl/geo-layers/typed/tileset-2d/types';
import type { GeoJsonLayerProps } from '@deck.gl/layers/typed';
import { parse } from '@loaders.gl/core';
import { MVTLoader } from '@loaders.gl/mvt';
import type { PMTilesTileSource } from '@loaders.gl/pmtiles';

// deck.gl 8.9's typed MVTLayer only accepts GeoJsonLayer styling props via ExtraProps.
type ExtraProps = Omit<GeoJsonLayerProps, 'data'> & {
  source: PMTilesTileSource;
  beforeId?: string;
};

// MVTLayer fetches `data` as TileJSON unless it looks like a {z}/{x}/{y}
// template. Tiles come from `source` instead, so `data` is only a placeholder.
const DATA_PLACEHOLDER = 'pmtiles://{z}/{x}/{y}';

/**
 * MVTLayer whose tiles are read from a PMTiles archive instead of tile URLs.
 * Clipping, picking and cross-tile highlighting are inherited unchanged.
 */
export default class PmtilesMvtLayer extends MVTLayer<ExtraProps> {
  static layerName = 'PmtilesMvtLayer';
  static defaultProps = { ...MVTLayer.defaultProps, data: DATA_PLACEHOLDER };

  async getTileData({ index }: TileLoadProps) {
    const buffer = await this.props.source.getTile(index);
    if (!buffer) return [];

    return parse(buffer, MVTLoader, {
      ...this.getLoadOptions(),
      mvt: {
        coordinates: 'local',
        tileIndex: index,
        shape: this.state.binary ? 'binary' : 'geojson',
      },
    });
  }
}
