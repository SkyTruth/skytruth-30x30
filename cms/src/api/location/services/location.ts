/**
 * location service
 */

import { factories } from '@strapi/strapi';

import { getLookupMap, type LookupIdField } from '../../../utils/lookup-map';

export default factories.createCoreService('api::location.location', () => ({
  getLocationMap(idField: LookupIdField) {
    return getLookupMap('api::location.location', 'code', idField, false);
  },
   mapRelations(relations: string[], locationsMap: IDMap): [string[], { err: string }[]] {
    const errors = [];
     
    const mappedRelations = relations.reduce((mapped, loc) => {
      const relationId = locationsMap[loc];
      if (!relationId) {
        errors.push({
          err: `Relationship ${loc} not found`
        });
      } else {
        mapped.push(relationId);
      };
      return mapped;
  }, [] as string[]);

    return [mappedRelations, errors];
  }
}));
