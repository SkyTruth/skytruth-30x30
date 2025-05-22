/**
 * pa router
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreRouter('api::pa.pa', {
<<<<<<< HEAD
  only: ['find', 'findOne', 'update', 'create',]
=======
  only: ['find', 'findOne', 'create', 'update'],
>>>>>>> feature/api-data-integration
});

