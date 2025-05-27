/**
 * environment service
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreService('api::environment.environment', ({ strapi }) => ({
  async getEnvironmentMap(): Promise<Record<string, any>> {
    const environments = await strapi.db.query('api::environment.environment').findMany({
      select: ['id', 'slug'],
      where: {locale: 'en'}
    });
    const environmentMap: Record<string, any> = {};
    environments.forEach((environment) => {
      environmentMap[environment.slug] = environment.id;
    }
    );
    return environmentMap;
  }
}));
