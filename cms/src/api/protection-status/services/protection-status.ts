/**
 * protection-status service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::protection-status.protection-status', 
  ({ strapi }) => ({
  async getProtectionStatusMap(): Promise<IDMap> {
    const statuses = await strapi.db.query('api::protection-status.protection-status').findMany({
      select: ['id', 'slug'],
    });

    const protectionStatusMap: IDMap = {};
    statuses.forEach((status) => {
      protectionStatusMap[status.slug] = status.id;
    });

    return protectionStatusMap;
  }
}));
