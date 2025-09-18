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
  }
}));
