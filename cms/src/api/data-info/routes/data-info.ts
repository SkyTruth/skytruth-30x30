/**
 * data-info router
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreRouter('api::data-info.data-info', {
    only: ['find', 'findOne', 'update', 'create']
});

