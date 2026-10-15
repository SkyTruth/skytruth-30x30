/**
 * mpaa-establishment-stage service
 */

import { factories } from '@strapi/strapi';

import { getLookupMap, type LookupIdField } from '../../../utils/lookup-map';

export default factories.createCoreService('api::mpaa-establishment-stage.mpaa-establishment-stage',
  () => ({
  getMpaaEstablishmentStageMap(idField: LookupIdField = 'documentId') {
    return getLookupMap('api::mpaa-establishment-stage.mpaa-establishment-stage', 'slug', idField, true);
  }
  }));
