/**
 * location service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::location.location', ({ strapi }) => ({
  async getLocationMap(): Promise<Record<string, any>> {
    const locations = await strapi.db.query('api::location.location').findMany({
      select: ['id', 'code'],
    });

    const locationMap: Record<string, any> = {};
    locations.forEach((location) => {
      locationMap[location.code] = location.id;
    });

    return locationMap;
  }
}));
