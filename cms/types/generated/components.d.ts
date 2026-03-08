import type { Schema, Struct } from '@strapi/strapi';

export interface DocumentationMetadata extends Struct.ComponentSchema {
  collectionName: 'components_documentation_metadata';
  info: {
    description: '';
    displayName: 'Metadata';
  };
  attributes: {
    citation: Schema.Attribute.RichText;
    content_date: Schema.Attribute.Date;
    description: Schema.Attribute.RichText & Schema.Attribute.Required;
    license: Schema.Attribute.String;
    resolution: Schema.Attribute.String;
    source: Schema.Attribute.RichText;
  };
}

export interface LegendLegend extends Struct.ComponentSchema {
  collectionName: 'components_legend_legends';
  info: {
    displayName: 'legend';
  };
  attributes: {
    items: Schema.Attribute.Component<'legend.legend-items', true>;
    type: Schema.Attribute.Enumeration<
      ['basic', 'icon', 'choropleth', 'gradient']
    >;
  };
}

export interface LegendLegendItems extends Struct.ComponentSchema {
  collectionName: 'components_legend_legend_items';
  info: {
    displayName: 'legend_items';
  };
  attributes: {
    color: Schema.Attribute.String;
    description: Schema.Attribute.String;
    icon: Schema.Attribute.String;
    value: Schema.Attribute.String & Schema.Attribute.Required;
  };
}

declare module '@strapi/strapi' {
  export module Public {
    export interface ComponentSchemas {
      'documentation.metadata': DocumentationMetadata;
      'legend.legend': LegendLegend;
      'legend.legend-items': LegendLegendItems;
    }
  }
}
