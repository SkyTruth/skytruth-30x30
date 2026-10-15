/**
 * mpa-iucn-category service
 */

import { factories } from '@strapi/strapi';

import { getLookupMap, type LookupIdField } from '../../../utils/lookup-map';

export default factories.createCoreService('api::mpa-iucn-category.mpa-iucn-category', () => ({
  getMpaaIucnCategoryMap(idField: LookupIdField = 'documentId') {
    return getLookupMap('api::mpa-iucn-category.mpa-iucn-category', 'slug', idField, true);
  }
}));

