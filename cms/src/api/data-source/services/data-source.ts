/**
 * data-source service
 */

import { factories } from '@strapi/strapi';

import { getLookupMap, type LookupIdField } from '../../../utils/lookup-map';

export default factories.createCoreService('api::data-source.data-source', () => ({
  getDataSourceMap(idField: LookupIdField) {
    return getLookupMap('api::data-source.data-source', 'slug', idField, true);
  }
}));
