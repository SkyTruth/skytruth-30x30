/**
 * mpaa-protection-level service
 */

import { factories } from '@strapi/strapi';

import { getLookupMap, type LookupIdField } from '../../../utils/lookup-map';

export default factories
.createCoreService('api::mpaa-protection-level.mpaa-protection-level', () => ({
  getMpaaProtectionLevelMap(idField: LookupIdField = 'documentId') {
    return getLookupMap('api::mpaa-protection-level.mpaa-protection-level', 'slug', idField, true);
  }
}));
