/**
 * fishing-protection-level service
 */

import { factories } from '@strapi/strapi';

export default factories
  .createCoreService('api::fishing-protection-level.fishing-protection-level', ({ strapi }) => ({
    async getFishingProtectionLevelMap(): Promise<IDMap> {
      const fishingProtectionLevels = await strapi.db
        .query('api::fishing-protection-level.fishing-protection-level')
        .findMany({
          select: ['id', 'slug'],
          where: {
            locale: 'en'
          }
        }) as { id: number; slug: string }[];

      const fishingProtectionLevelMap: IDMap = {};
      fishingProtectionLevels.forEach((level) => {
        fishingProtectionLevelMap[level.slug] = level.id;
      });
      return fishingProtectionLevelMap;
    }
  }));

