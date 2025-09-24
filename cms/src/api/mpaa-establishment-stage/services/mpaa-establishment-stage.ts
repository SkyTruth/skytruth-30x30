/**
 * mpaa-establishment-stage service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::mpaa-establishment-stage.mpaa-establishment-stage',
  ({ strapi }) => ({
  async getMpaaEstablishmentStageMap(): Promise<IDMap> {
    const stages = await strapi.db.query('api::mpaa-establishment-stage.mpaa-establishment-stage')
    .findMany({
      select: ['id', 'slug'],
    });

    const mpaaIucnCategoryMap: IDMap = {};
    stages.forEach((stage) => {
      mpaaIucnCategoryMap[stage.slug] = stage.id;
    });

    return mpaaIucnCategoryMap;
  }
  }));
