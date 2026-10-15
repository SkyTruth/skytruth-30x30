/**
 * environment service
 */

import { factories } from '@strapi/strapi';

import { getLookupMap, type LookupIdField } from '../../../utils/lookup-map';


export default factories.createCoreService('api::environment.environment', () => ({
  getEnvironmentMap(idField: LookupIdField = 'documentId') {
    return getLookupMap('api::environment.environment', 'slug', idField, true);
  }
}));
