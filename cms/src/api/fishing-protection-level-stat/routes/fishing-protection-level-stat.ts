/**
 * fishing-protection-level-stat router
 */

import { factories } from '@strapi/strapi';

export default factories.createCoreRouter('api::fishing-protection-level-stat.fishing-protection-level-stat', {
    only: ['find', 'findOne', 'update', 'create']
});
