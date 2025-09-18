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
    },
    async getAggregatedStats(locations: string[], mpaa_protection_level: string = null) {
      console.log("protection level", mpaa_protection_level)
    const stats = await strapi.db.query('api::mpaa-protection-level-stat.mpaa-protection-level-stat').findMany({
      where: {
          ...(mpaa_protection_level ? {
            mpaa_protection_level : {
              slug: mpaa_protection_level
            } 
          } : {}),
          location: {
            code: {
              $in: locations
            }
          },
        },
        populate: {
          mpaa_protection_level: {
            fields: "slug"
          }
        },
    })
      const aggregatedStats = stats.reduce((acc, stat) => {
        const protectionLevel = stat.mpaa_protection_level.slug;
        let totalArea = +stat.total_area;

        if (!totalArea) {
          totalArea = (stat.protected_area * 100) / stat.coverage;
        }

        if (!acc[protectionLevel]) {
          acc[protectionLevel] = {
            mpaa_protection_level,
            total_area: 0,
            protected_area: 0,
            records: 0
          };
        }

        acc[protectionLevel].total_area += totalArea;
        acc[protectionLevel].protected_area += stat.area;
        acc[protectionLevel].records++;
        acc[protectionLevel].coverage = 
          (acc[protectionLevel].protected_area / acc[protectionLevel].total_area) * 100;
        return acc;
      }, {})

    return Object.values(aggregatedStats);
  }
}));
