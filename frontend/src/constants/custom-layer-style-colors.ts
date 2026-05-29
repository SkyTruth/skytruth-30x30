export const CUSTOM_LAYER_STYLE_COLORS = [
  { value: '#86A6F0', nameKey: 'periwinkle-blue' },
  { value: '#89D8EA', nameKey: 'light-blue' },
  { value: '#81D291', nameKey: 'mint-green' },
  { value: '#F6C534', nameKey: 'saffron-yellow' },
  { value: '#DE4238', nameKey: 'brick-red' },
] as const;

export type CustomLayerStyleColorOption = (typeof CUSTOM_LAYER_STYLE_COLORS)[number];
