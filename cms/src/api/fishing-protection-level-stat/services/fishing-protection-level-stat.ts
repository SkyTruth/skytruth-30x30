/**
 * fishing-protection-level-stat service
 */

import { factories } from '@strapi/strapi';

export type FishingProtectionLevelStatMap = {
  [key: string]: number // Maps fishing protection level slug and location code to ID
};

export default factories
.createCoreService('api::fishing-protection-level-stat.fishing-protection-level-stat', ({ strapi }) => ({
  async getFishingProtectionLevelStatsMap(): Promise<FishingProtectionLevelStatMap> {
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
    const fishingProtectionLevelStatsMap: FishingProtectionLevelStatMap = {};
    stats.forEach((stat) => {
      if (stat?.location !== null && stat?.fishing_protection_level !== null) {
        fishingProtectionLevelStatsMap[`${stat.location.code}-${stat.fishing_protection_level.slug}`] = stat.id;
      }
    });
    return fishingProtectionLevelStatsMap;
  }
}));;
