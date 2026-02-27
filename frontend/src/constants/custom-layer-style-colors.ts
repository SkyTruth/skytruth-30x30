export const CUSTOM_LAYER_STYLE_COLORS = [
  { value: '#86a6f0', nameKey: 'soft-blue' },
  { value: '#a9db93', nameKey: 'soft-green' },
  { value: '#dde44f', nameKey: 'soft-lime' },
  { value: '#d55d55', nameKey: 'muted-red' },
  { value: '#c95aa8', nameKey: 'muted-pink' },
] as const;

export type CustomLayerStyleColorOption = (typeof CUSTOM_LAYER_STYLE_COLORS)[number];
