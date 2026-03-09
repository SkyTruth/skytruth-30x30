/**
 * protection-coverage-stat service
 */

import { factories } from '@strapi/strapi';

import { PROTECTION_COVERAGE_STAT_NAMESPACE } from '../controllers/protection-coverage-stat';

type StatsMapStats = {
  documentId: string,
  is_last_year: boolean, 
  location: {
    code: string,
    documentId: string
  }, 
  environment: {
    slug: string
    documentId: string
  }
}

export default factories.createCoreService('api::protection-coverage-stat.protection-coverage-stat', 
  ({ strapi }) => ({
    async getStatsMap(year: number): Promise<IDMap> {
      const stats = await strapi.documents(PROTECTION_COVERAGE_STAT_NAMESPACE).findMany({
          filters: { year },
          fields:['documentId', 'is_last_year'],
          populate: {
              location: {
                  fields: ['code']
              },
              environment: {
                  fields: ['slug']
              }
          }
      }) as StatsMapStats[];

      const statsMap: IDMap = {};
      stats.forEach((stat) => {
        if (!stat.location || !stat.environment) {
          strapi.log.warn(`Protection coverage stat with ID ${stat.documentId} is missing location or environment.`);
          return;
        }
        statsMap[`${stat.location.code}-${stat.environment.slug}`] = stat.documentId;
      });

      return statsMap;
  }
}));
