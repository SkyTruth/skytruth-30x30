/**
 * habitat service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::habitat.habitat', ({ strapi }) => ({
  async getHabitatMap(): Promise<IDMap> {
    const habitats = await strapi.db.query('api::habitat.habitat').findMany({
      select: ['id', 'slug'],
      where: {
        locale: 'en'
      }
    }) as { id: number, slug: string }[];

    const habitatMap: IDMap = {};
    habitats.forEach((habitat) => {
      habitatMap[habitat.slug] = habitat.id;
    });

    return habitatMap;
  }
}));
