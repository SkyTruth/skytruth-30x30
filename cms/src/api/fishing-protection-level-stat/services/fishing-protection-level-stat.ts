/**
 * fishing-protection-level-stat service
 */

import { factories } from '@strapi/strapi';

export default factories
.createCoreService('api::fishing-protection-level-stat.fishing-protection-level-stat', ({ strapi }) => ({
  async getFishingProtectionLevelStatsMap(): Promise<IDMap> {
    const stats = await strapi.entityService.findMany(
        'api::fishing-protection-level-stat.fishing-protection-level-stat',
        {
          fields:  ['id'],
          populate: {
            location: {
              fields: ['code']
            },
            fishing_protection_level: {
              fields: ['slug']
            }
          }
        }) as { id: number, location: { code: string }, fishing_protection_level: { slug: string } }[];
    const fishingProtectionLevelStatsMap: IDMap = {};
    stats.forEach((stat) => {
      if (stat?.location !== null && stat?.fishing_protection_level !== null) {
        fishingProtectionLevelStatsMap[`${stat.location.code}-${stat.fishing_protection_level.slug}`] = stat.id;
      }
    });
    return fishingProtectionLevelStatsMap;
  },
  async getAggregatedStats(locations: string[], fishing_protection_level: string = null) {
    const stats = await strapi.db.query('api::fishing-protection-level-stat.fishing-protection-level-stat').findMany({
      where: {
          ...(fishing_protection_level ? {
            fishing_protection_level : {
              slug: fishing_protection_level
            } 
          } : {}),
          location: {
            code: {
              $in: locations
            }
          },
        },
        populate: {
          fishing_protection_level: {
            fields: "slug"
          }
        },
    })
      const aggregatedStats = stats.reduce((acc, stat) => {
        const fishingLevel = stat.fishing_protection_level.slug;
        let totalArea = +stat.total_area;

        if (!totalArea) {
          totalArea = (stat.protected_area * 100) / stat.coverage;
        }

        if (!acc[fishingLevel]) {
          acc[fishingLevel] = {
            fishing_protection_level,
            total_area: 0,
            protected_area: 0,
            records: 0
          };
        }

        acc[fishingLevel].total_area += totalArea;
        acc[fishingLevel].protected_area += stat.parea;
        acc[fishingLevel].records++;
        acc[fishingLevel].coverage = 
          (acc[fishingLevel].protected_area / acc[fishingLevel].total_area) * 100;
        return acc;
      }, {})

    return Object.values(aggregatedStats);
  }
}));;
