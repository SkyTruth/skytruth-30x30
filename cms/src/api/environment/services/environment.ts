/**
 * environment service
 */

import { factories } from '@strapi/strapi';


export default factories.createCoreService('api::environment.environment', ({ strapi }) => ({
  async getEnvironmentMap(): Promise<IDMap> {
    const environments = await strapi.db.query('api::environment.environment').findMany({
      select: ['id', 'slug'],
      where: {locale: 'en'}
    }) as { id: number; slug: string }[];

    const environmentMap: IDMap = {};
    environments.forEach((environment) => {
      environmentMap[environment.slug] = environment.id;
    }
    );
    return environmentMap;
  }
}));
