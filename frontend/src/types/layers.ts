import type { AnyLayer, AnySource } from 'react-map-gl';

import { GeoJSON } from 'geojson';
import { z } from 'zod';

import { FormatProps } from '@/lib/utils/formats';
import type { Layer } from '@/types/generated/strapi.schemas';

export type Config = {
  source: AnySource;
  styles: AnyLayer[];
};

export type ParamsConfigValue = {
  key: string;
  default: unknown;
};

export type ParamsConfig = ParamsConfigValue[];

export type LegendConfig = {
  type?: 'basic' | 'icon' | 'gradient' | 'choropleth';
  items?: {
    value?: string;
    icon?: string;
    color?: string;
    description?: string;
  }[];
};

export type InteractionConfig = {
  enabled: boolean;
  events: {
    type: 'click' | 'hover';
    values: {
      key: string;
      label: string;
      format?: FormatProps;
    }[];
  }[];
};

export type LayerProps = {
  id?: string;
  zIndex?: number;
  onAdd?: (props: Config) => void;
  onRemove?: (props: Config) => void;
};

export const layerSettingsSchema = z.record(
  z.string(),
  z.object({
    opacity: z.number().optional(),
    visibility: z.boolean().optional(),
    expand: z.boolean().optional(),
  })
);

export type LayerSettings = z.infer<typeof layerSettingsSchema>;

export type LayerTyped = Layer & {
  config: Config;
  params_config: ParamsConfig;
  legend_config: LegendConfig;
  interaction_config: InteractionConfig;
  metadata: Record<string, unknown>;
};

export type UserLayer = {
  name: string;
  geoJSON: GeoJSON;
};
