/**
 * fishing-protection-level service
 */

import { factories } from '@strapi/strapi';

export type FishingProtectionLevelMap = {
  [key: string]: number; // Maps fishing protection level slug to ID
};

export default factories
  .createCoreService('api::fishing-protection-level.fishing-protection-level', ({ strapi }) => ({
    async getFishingProtectionLevelMap(): Promise<FishingProtectionLevelMap> {
      const fishingProtectionLevels = await strapi.db
        .query('api::fishing-protection-level.fishing-protection-level')
        .findMany({
          select: ['id', 'slug'],
          where: {
            locale: 'en'
          }
        }) as { id: number; slug: string }[];
      const fishingProtectionLevelMap: FishingProtectionLevelMap = {};
      fishingProtectionLevels.forEach((level) => {
        fishingProtectionLevelMap[level.slug] = level.id;
      });
      return fishingProtectionLevelMap;
    }
  }));

