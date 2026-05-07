/**
 * location service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::location.location', ({ strapi }) => ({
  async getLocationMap(): Promise<IDMap> {
    const locations = await strapi.db.query('api::location.location').findMany({
      select: ['documentId', 'code'],
    });

    const locationMap: IDMap = {};
    locations.forEach((location) => {
      locationMap[location.code] = location.documentId;
    });

    return locationMap;
  },
   mapRelations(relations: string[], locationsMap: IDMap): [string[], { err: string }[]] {
    const errors = [];
     
    const mappedRelations = relations.reduce((mapped, loc) => {
      const relationId = locationsMap[loc];
      if (!relationId) {
        errors.push({
          err: `Relationship ${loc} not found`
        });
      } else {
        mapped.push(relationId);
      };
      return mapped;
  }, [] as string[]);

    return [mappedRelations, errors];
  }
}));
