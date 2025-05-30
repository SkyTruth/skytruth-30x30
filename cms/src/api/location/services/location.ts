/**
 * location service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::location.location', ({ strapi }) => ({
  async getLocationMap(): Promise<IDMap> {
    const locations = await strapi.db.query('api::location.location').findMany({
      select: ['id', 'code'],
    });

    const locationMap: IDMap = {};
    locations.forEach((location) => {
      locationMap[location.code] = location.id;
    });

    return locationMap;
  }
}));
