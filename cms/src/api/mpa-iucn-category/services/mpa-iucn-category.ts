/**
 * mpa-iucn-category service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::mpa-iucn-category.mpa-iucn-category', ({ strapi }) => ({
  async getMpaaIucnCategoryMap(): Promise<IDMap> {
    const categories = await strapi.db.query('api::mpa-iucn-category.mpa-iucn-category').findMany({
      select: ['id', 'slug'],
    });

    const mpaaIucnCategoryMap: IDMap = {};
    categories.forEach((category) => {
      mpaaIucnCategoryMap[category.slug] = category.id;
    });

    return mpaaIucnCategoryMap;
  }
}));

