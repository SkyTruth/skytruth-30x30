/**
 * data-source router
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreRouter('api::data-source.data-source', {
    only: ['find', 'findOne', 'update', 'create']
});

