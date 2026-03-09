/**
 * habitat service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::habitat.habitat', ({ strapi }) => ({
  async getHabitatMap(): Promise<IDMap> {
    const habitats = await strapi.db.query('api::habitat.habitat').findMany({
      select: ['documentId', 'slug'],
      where: {
        locale: 'en'
      }
    }) as { documentId: string, slug: string }[];

    const habitatMap: IDMap = {};
    habitats.forEach((habitat) => {
      habitatMap[habitat.slug] = habitat.documentId;
    });

    return habitatMap;
  }
}));
