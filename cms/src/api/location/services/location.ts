/**
 * location service
 */

import { factories } from '@strapi/strapi';

export type LocationMap = {
  [code: string]: number; // Maps location code to location ID
}

export default factories.createCoreService('api::location.location', ({ strapi }) => ({
  async getLocationMap(): Promise<Record<string, any>> {
    const locations = await strapi.db.query('api::location.location').findMany({
      select: ['id', 'code'],
    });

    const locationMap: LocationMap = {};
    locations.forEach((location) => {
      locationMap[location.code] = location.id;
    });

    return locationMap;
  }
}));
