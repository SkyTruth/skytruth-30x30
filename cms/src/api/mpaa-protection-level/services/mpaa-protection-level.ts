/**
 * mpaa-protection-level service
 */

import { factories } from '@strapi/strapi';

export type LocationMap = {
  [slug: string]: number; // Maps MPAA protection level slug to ID
}

export default factories
.createCoreService('api::mpaa-protection-level.mpaa-protection-level', ({ strapi }) => ({
  async getMpaaProtectionLevelMap(): Promise<LocationMap> {
    const mpaaProtectionLevels = await strapi.db.query('api::mpaa-protection-level.mpaa-protection-level').findMany({
      select: ['id', 'slug'],
      where: {
        locale: 'en'
      }
    });
    const mpaaProtectionLevelMap: LocationMap = {};
    mpaaProtectionLevels.forEach((level) => {
      mpaaProtectionLevelMap[level.slug] = level.id;
    }
    );
    return mpaaProtectionLevelMap;
  }
}));
