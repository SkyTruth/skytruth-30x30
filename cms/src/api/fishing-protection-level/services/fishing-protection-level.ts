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
          select: ['documentId', 'slug'],
          where: {
            locale: 'en'
          }
        }) as { documentId: string; slug: string }[];

      const fishingProtectionLevelMap: IDMap = {};
      fishingProtectionLevels.forEach((level) => {
        fishingProtectionLevelMap[level.slug] = level.documentId;
      });
      return fishingProtectionLevelMap;
    }
  }));

