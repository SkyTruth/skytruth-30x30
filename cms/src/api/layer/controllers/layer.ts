/**
 * layer controller
 */

import { TERRITORY_LAYERS } from '../../../utils/constants';

import { factories } from '@strapi/strapi'

export default factories.createCoreController('api::layer.layer', ({ strapi }) => ({
  // TODO TECH-3174: Clean up
  async find(ctx) {
    const response = await super.find(ctx);

    const areTerritoriesActive = await strapi
      .service('api::feature-flag.feature-flag')
      .getFeaureFlag(ctx, 'are_territories_active');
      
    const filteredData = response.data.filter(layer => {
      const layerUrl =  layer?.attributes?.config?.source?.url;
      const layerSlug = layer?.attributes?.slug;
      return (
        (!areTerritoriesActive &&
          (!TERRITORY_LAYERS[layerSlug] || TERRITORY_LAYERS[layerSlug] !== layerUrl)) ||
        (areTerritoriesActive &&
          (!TERRITORY_LAYERS[layerSlug]  || TERRITORY_LAYERS[layerSlug] === layerUrl))
      );
    });

    response.data = filteredData;
    return response;
  }
}));
