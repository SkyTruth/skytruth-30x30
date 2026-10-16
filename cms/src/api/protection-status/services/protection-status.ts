/**
 * protection-status service
 */

import { factories } from '@strapi/strapi';

import { getLookupMap, type LookupIdField } from '../../../utils/lookup-map';

export default factories.createCoreService('api::protection-status.protection-status', 
  () => ({
  getProtectionStatusMap(idField: LookupIdField) {
    return getLookupMap('api::protection-status.protection-status', 'slug', idField, true);
  }
}));
