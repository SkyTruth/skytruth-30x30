/**
 * habitat-stat service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::habitat-stat.habitat-stat', ({ strapi }) => ({
  async getHabitatStatMap(year: number): Promise<IDMap> {
    const habitatStats = await strapi.entityService.findMany('api::habitat-stat.habitat-stat', {
      filters: { 
        year,
        locale: 'en',
      },
      fields: ['id'],
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
    }) as { id: number, location: { code: string }, environment: { slug: string }, habitat: { slug: string } }[];

    const statsMap: IDMap = {};
    habitatStats.forEach((stat) => {
      if (!stat.location || !stat.environment || !stat.habitat) {
        strapi.log.warn(`Habitat stat with ID ${stat.id} is missing location, environment, or habitat.`);
        return;
      }
      statsMap[`${stat.location.code}-${stat.environment.slug}-${stat.habitat.slug}`] = stat.id
    });
    return statsMap;
  },
}));
