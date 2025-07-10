/**
 * location router
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreRouter('api::location.location', {
    only: ['find', 'findOne', 'update', 'create']
});
