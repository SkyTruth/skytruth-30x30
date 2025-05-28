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
            // this is all we track now, hardcoding it make sure nothing weird gets added by accident
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
    // console.log(stats)
      const statsMap: Record<string, any> = {};
      for (const stat of stats) {
        if (stat?.location !== null && stat?.mpaa_protection_level !== null) {
          statsMap[`${stat.location.code}-${stat.mpaa_protection_level.slug}`] = stat.id;
        }
      };
      console.log("SM", statsMap);
      return statsMap;
    }
}));


/**
 * Dont assume record exists, make this endpoint an upser!!!
 */
