import { MVTLayer } from '@deck.gl/geo-layers/typed';
import type { TileLoadProps } from '@deck.gl/geo-layers/typed/tileset-2d/types';
import { GeoJsonLayer } from '@deck.gl/layers/typed';
import { parse } from '@loaders.gl/core';
import { MVTLoader } from '@loaders.gl/mvt';
import type { PMTilesTileSource } from '@loaders.gl/pmtiles';

import { type CompiledStyle, type RGBAColor, toStyleFeature } from './style-interpreter';

type ExtraProps = {
  source: PMTilesTileSource;
  styles: CompiledStyle[];
  beforeId?: string;
};

// MVTLayer fetches `data` as TileJSON unless it looks like a {z}/{x}/{y}
// template. Tiles come from `source` instead, so `data` is only a placeholder.
const DATA_PLACEHOLDER = 'pmtiles://{z}/{x}/{y}';

const TRANSPARENT: RGBAColor = [0, 0, 0, 0];

/**
 * MVTLayer whose tiles are read from a PMTiles archive and drawn as one
 * GeoJsonLayer per Mapbox style layer. Clipping, picking and cross-tile
 * highlighting are inherited unchanged.
 */
export default class PmtilesMvtLayer extends MVTLayer<ExtraProps> {
  static layerName = 'PmtilesMvtLayer';
  static defaultProps = { ...MVTLayer.defaultProps, data: DATA_PLACEHOLDER };

  async getTileData({ index }: TileLoadProps) {
    const buffer = await this.props.source.getTile(index);
    if (!buffer) return [];
    // Parsed with loaders.gl 4.x while deck.gl 8.9's MVTLayer bundles 3.x; the
    // binary tile shape is compatible across the two. GeoJSON output on 4.x
    // lacks `feature.id`, so non-binary layers need `uniqueIdProperty` for
    // cross-tile highlighting.
    return parse(buffer, MVTLoader, {
      ...this.getLoadOptions(),
      mvt: {
        coordinates: 'local',
        tileIndex: index,
        shape: this.state.binary ? 'binary' : 'geojson',
      },
    });
  }

  renderSubLayers(props: Parameters<MVTLayer['renderSubLayers']>[0]) {
    // MVTLayer builds one GeoJsonLayer carrying the tile transform and clip
    // extension; clone it per style so those props stay intact. Features that
    // fail a style's filter are drawn fully transparent rather than removed, so
    // the highlight index MVTLayer computes against the full tile stays valid.
    const base = super.renderSubLayers(props);
    if (!(base instanceof GeoJsonLayer)) return base;

    const { styles } = this.props;
    const zoom = props.tile.index.z;
    const state = {};

    return styles.map((style) => {
      const color = (object: Parameters<typeof toStyleFeature>[0]) => {
        const feature = toStyleFeature(object);
        return style.matches(feature, zoom) ? style.color(feature, state, zoom) : TRANSPARENT;
      };
      return base.clone({
        id: `${props.id}-${style.id}`,
        visible: base.props.visible && style.visible,
        filled: style.type === 'fill',
        stroked: style.type === 'line',
        getFillColor: color,
        getLineColor: color,
        getLineWidth: (object) => {
          const feature = toStyleFeature(object);
          return style.matches(feature, zoom) ? style.lineWidth(feature, state, zoom) : 0;
        },
        lineWidthUnits: 'pixels',
        updateTriggers: {
          getFillColor: [styles, zoom],
          getLineColor: [styles, zoom],
          getLineWidth: [styles, zoom],
        },
      });
    });
  }
}
