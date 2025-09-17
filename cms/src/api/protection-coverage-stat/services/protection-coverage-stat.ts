/**
 * protection-coverage-stat service
 */

import { factories } from '@strapi/strapi';

import { PROTECTION_COVERAGE_STAT_NAMESPACE } from '../controllers/protection-coverage-stat';

type StatsMapStats = {
  id: number, 
  is_last_year: boolean, 
  location: {
    code: string,
    id: number
  }, 
  environment: {
    slug: string
    id: number
  }
}

export default factories.createCoreService('api::protection-coverage-stat.protection-coverage-stat', 
  ({ strapi }) => ({
    async getStatsMap(year: number): Promise<IDMap> {
      const stats = await strapi.entityService.findMany(
        PROTECTION_COVERAGE_STAT_NAMESPACE,
        {
            filters: { year },
            fields:['id', 'is_last_year'],
            populate: {
                location: {
                    fields: ['code']
                },
                environment: {
                    fields: ['slug']
                }
            }
        }
      ) as StatsMapStats[];

      const statsMap: IDMap = {};
      stats.forEach((stat) => {
        if (!stat.location || !stat.environment) {
          strapi.log.warn(`Protection coverage stat with ID ${stat.id} is missing location or environment.`);
          return;
        }
        statsMap[`${stat.location.code}-${stat.environment.slug}`] = stat.id
      });

      return statsMap;
  },
  async getAggregatedStats(locations: string[], environment: string = null, year: number = null) {
    const stats = await strapi.db.query(PROTECTION_COVERAGE_STAT_NAMESPACE).findMany({
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
        },
        orderBy: {
          year: 'asc'
        }
    })
      const aggregatedStats = stats.reduce((acc, stat) => {
        const environment = stat.environment.slug;
        const year = stat.year;
        let totalArea = +stat.total_area;

        if (!totalArea) {
          totalArea = (stat.protected_area * 100) / stat.coverage;
        }

        const statKey = `${year}-${environment}`;
        if (!acc[statKey]) {
          acc[statKey] = {
            year,
            environment,
            total_area: 0,
            protected_area: 0,
            records: 0
          };
        }

        acc[statKey].total_area += totalArea;
        acc[statKey].protected_area += stat.protected_area;
        acc[statKey].records++;
        acc[statKey].coverage = 
          (acc[statKey].protected_area / acc[statKey].total_area) * 100;
        return acc;
      }, {})

    return Object.values(aggregatedStats);
  }

}));
