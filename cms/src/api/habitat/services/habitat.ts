/**
 * habitat service
 */

import { factories } from '@strapi/strapi';

export type HabitatMap = {
  id: number; // Maps habitat slug to ID
};

export default factories.createCoreService('api::habitat.habitat', ({ strapi }) => ({
  async getHabitatMap(): Promise<Record<string, number>> {
    const habitats = await strapi.db.query('api::habitat.habitat').findMany({
      select: ['id', 'slug'],
      where: {
        locale: 'en'
      }
    }) as { id: number, slug: string }[];
    const habitatMap: Record<string, number> = {};
    habitats.forEach((habitat) => {
      habitatMap[habitat.slug] = habitat.id;
    });
    return habitatMap;
  }
}));
