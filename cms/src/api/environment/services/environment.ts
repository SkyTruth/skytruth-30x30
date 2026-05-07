/**
 * environment service
 */

import { factories } from '@strapi/strapi';


export default factories.createCoreService('api::environment.environment', ({ strapi }) => ({
  async getEnvironmentMap(): Promise<IDMap> {
    const environments = await strapi.db.query('api::environment.environment').findMany({
      select: ['documentId', 'slug'],
      where: {locale: 'en'}
    }) as { documentId: string; slug: string }[];

    const environmentMap: IDMap = {};
    environments.forEach((environment) => {
      environmentMap[environment.slug] = environment.documentId;
    }
    );
    return environmentMap;
  }
}));
