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
  async getAggregatedStats(locations: string[], environment: string = null, year: number = null) {
    const stats = await strapi.db.query("api::habitat-stat.habitat-stat").findMany({
          where: {
              ...(year ? { year } : {}),
              location: {
                code: {
                  $in: locations
                }
              },
              ...(environment? { environment: {slug: environment} } : {})
            },
            populate: {
              environment: {
                fields: "slug"
              },
              habitat: {
                fields: "slug"
              }
            },
            orderBy: {
              year: 'asc'
            }
        })
          const aggregatedStats = stats.reduce((acc, stat) => {
            const environment = stat.environment.slug;
            const year = stat.year;
            const habitat = stat.habitat.slug;
            let totalArea = +stat.total_area;
    
            if (!totalArea) {
              totalArea = (stat.protected_area * 100) / stat.coverage;
            }
    
            const recordKey = `${year}-${environment}-${habitat}`
            if (!acc[recordKey]) {
              acc[recordKey] = {
                year,
                environment,
                habitat,
                total_area: 0,
                protected_area: 0,
                records: 0
              };
            }
    
            acc[recordKey].total_area += totalArea;
            acc[recordKey].protected_area += stat.protected_area;
            acc[recordKey].records++;
            acc[recordKey].coverage = 
              (acc[recordKey].protected_area / acc[recordKey].total_area) * 100;
            return acc;
          }, {})
    
        return Object.values(aggregatedStats);
  }
}));
