/**
 * habitat-stat service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::habitat-stat.habitat-stat', ({ strapi }) => ({
  async getStatsMap(year: number): Promise<IDMap> {
    const stats = await strapi.entityService.findMany('api::habitat-stat.habitat-stat', {
      filters: { year },
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
    stats.forEach((stat) => {
      if (!stat.location || !stat.environment || !stat.habitat) {
        strapi.log.warn(`Habitat stat with ID ${stat.id} is missing location, environment, or habitat.`);
        return;
      }
      statsMap[`${stat.location.code}-${stat.environment.slug}-${stat.habitat.slug}`] = stat.id
    });

    return statsMap;
  },
}));
