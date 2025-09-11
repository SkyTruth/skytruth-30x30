/**
 * data-source service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::data-source.data-source', ({ strapi }) => ({
  async getDataSourceMap(): Promise<IDMap> {
    const sources = await strapi.db.query('api::data-source.data-source').findMany({
      select: ['id', 'slug'],
    });

    const dataSourceMap: IDMap = {};
    sources.forEach((source) => {
      dataSourceMap[source.slug] = source.id;
    });

    return dataSourceMap;
  }
}));
