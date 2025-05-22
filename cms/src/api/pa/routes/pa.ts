/**
 * pa router
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreRouter('api::pa.pa', {
  only: ['find', 'findOne', 'create', 'update'],
});

