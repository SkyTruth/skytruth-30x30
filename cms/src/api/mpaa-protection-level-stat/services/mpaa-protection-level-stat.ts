/**
 * mpaa-protection-level-stat service
 */

import { factories } from '@strapi/strapi';

export default factories
  .createCoreService('api::mpaa-protection-level-stat.mpaa-protection-level-stat', ({ strapi }) => ({
    async getStatsMap(): Promise<Record<string, any>> {
      const stats = await strapi.entityService.findMany(
        'api::mpaa-protection-level-stat.mpaa-protection-level-stat',
        {
          filters: {
            // this is all we track now, if we expand, level can be part of the map key
            mpaa_protection_level: { slug: 'fully-highly-protected' }
          },
          fields:  ['id'],
          populate: {
            location: {
              fields: ['code']
            },
            mpaa_protection_level: {
              fields: ['slug']
            }
          }
        } 
      ) as { id: number, location: { code: string }, mpaa_protection_level: { slug: string } }[];

      const statsMap: Record<string, any> = {};
      for (const stat of stats) {
        if (stat?.location !== null && stat?.mpaa_protection_level !== null) {
          statsMap[`${stat.location.code}-${stat.mpaa_protection_level.slug}`] = stat.id;
        }
      };
      return statsMap;
    }
}));
