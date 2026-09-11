import type { AnyLayer } from 'react-map-gl';

import { expression, featureFilter, latest } from '@mapbox/mapbox-gl-style-spec';

export type RGBAColor = [number, number, number, number];

type StyleFeature = { type: 'Unknown'; properties: Record<string, unknown> };
type FeatureState = Record<string, unknown>;
type Evaluate<T> = (feature: StyleFeature, state: FeatureState, zoom: number) => T;

export interface CompiledStyle {
  id: string;
  type: 'fill' | 'line';
  visible: boolean;
  /** True when the feature passes both `source-layer` and `filter` */
  matches: (feature: StyleFeature, zoom: number) => boolean;
  /** RGBA 0–255 with the paint opacity folded into the alpha channel */
  color: Evaluate<RGBAColor>;
  /** Pixels; always 0 for fill styles */
  lineWidth: Evaluate<number>;
}

const SPECS = {
  fill: {
    color: latest.paint_fill['fill-color'],
    opacity: latest.paint_fill['fill-opacity'],
  },
  line: {
    color: latest.paint_line['line-color'],
    opacity: latest.paint_line['line-opacity'],
    width: latest.paint_line['line-width'],
  },
};

const SUPPORTED_PAINT = {
  fill: ['fill-color', 'fill-opacity'],
  line: ['line-color', 'line-width', 'line-opacity'],
};

const warned = new Set<string>();
const warnOnce = (message: string) => {
  if (warned.has(message)) return;
  warned.add(message);
  console.warn(`[pmtiles styles] ${message}`);
};

type PropertySpec = { default?: unknown };
type StyleExpression = InstanceType<typeof expression.StyleExpression>;

const compile = (id: string, name: string, value: unknown, spec: PropertySpec) => {
  const result = expression.createExpression(value ?? spec.default, spec as never);
  if (result.result === 'success') return result.value;
  warnOnce(
    `${id}: invalid ${name}, using default (${result.value.map((e) => e.message).join('; ')})`
  );
  return expression.createExpression(spec.default, spec as never).value as StyleExpression;
};

export const toStyleFeature = (object: { properties?: Record<string, unknown> | null }) => ({
  type: 'Unknown' as const,
  properties: object.properties ?? {},
});

export const compileStyles = (styles: AnyLayer[]): CompiledStyle[] =>
  styles.flatMap((style) => {
    if (style.type !== 'fill' && style.type !== 'line') {
      warnOnce(`${style.id}: style type "${style.type}" is not supported`);
      return [];
    }
    const { type } = style;
    const paint = (style.paint ?? {}) as Record<string, unknown>;
    const layout = (style.layout ?? {}) as Record<string, unknown>;

    for (const key of Object.keys(paint)) {
      if (!SUPPORTED_PAINT[type].includes(key)) warnOnce(`${style.id}: paint "${key}" is ignored`);
    }
    for (const key of Object.keys(layout)) {
      if (key !== 'visibility') warnOnce(`${style.id}: layout "${key}" is ignored`);
    }

    const colorExpr = compile(style.id, `${type}-color`, paint[`${type}-color`], SPECS[type].color);
    const opacityExpr = compile(
      style.id,
      `${type}-opacity`,
      paint[`${type}-opacity`],
      SPECS[type].opacity
    );
    const widthExpr =
      type === 'line'
        ? compile(style.id, 'line-width', paint['line-width'], SPECS.line.width)
        : null;
    const { filter } = featureFilter(style.filter);
    const sourceLayer = style['source-layer'];

    return [
      {
        id: style.id,
        type,
        visible: layout.visibility !== 'none',
        matches: (feature, zoom) =>
          (!sourceLayer || feature.properties.layerName === sourceLayer) &&
          filter({ zoom }, feature),
        color: (feature, state, zoom) => {
          const { r, g, b, a } = colorExpr
            .evaluate({ zoom }, feature, state)
            .toNonPremultipliedRenderColor(null);
          const opacity = opacityExpr.evaluate({ zoom }, feature, state) as number;
          return [r * 255, g * 255, b * 255, a * opacity * 255];
        },
        lineWidth: (feature, state, zoom) =>
          widthExpr ? (widthExpr.evaluate({ zoom }, feature, state) as number) : 0,
      },
    ];
  });
