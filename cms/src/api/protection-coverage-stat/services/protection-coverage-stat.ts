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
    async getStatsMap(year: number): Promise<Record<string, any>> {
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

      const statsMap: Record<string, any> = {};
      stats.forEach((stat) => {
        statsMap[`${stat.location.code}-${stat.environment.slug}`] = {
          id: stat.id,
          is_last_year: stat.is_last_year,
          locatioon: stat.location.id
        }
      });

      return statsMap;
    }
}));
