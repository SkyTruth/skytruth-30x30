/**
 * habitat-stat service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::habitat-stat.habitat-stat', ({ strapi }) => ({
  async getHabitatStatMap(year: number): Promise<IDMap> {
    const habitatStats = await strapi.documents('api::habitat-stat.habitat-stat').findMany({
      filters: { 
        year,
        locale: 'en',
      },
      fields: ['documentId'],
      populate: {
        location: {
          fields: ['code'],
        },
        environment: {
          fields: ['slug'],
        },
        habitat:{
          fields: ['slug']
        }
      },
    }) as { documentId: string, location: { code: string }, environment: { slug: string }, habitat: { slug: string } }[];

    const statsMap: IDMap = {};
    habitatStats.forEach((stat) => {
      if (!stat.location || !stat.environment || !stat.habitat) {
        strapi.log.warn(`Habitat stat with ID ${stat.documentId} is missing location, environment, or habitat.`);
        return;
      }
      statsMap[`${stat.location.code}-${stat.environment.slug}-${stat.habitat.slug}`] = stat.documentId;
    });
    return statsMap;
  },
}));
