/**
 * location controller
 */

import { factories } from '@strapi/strapi'

export default factories.createCoreController('api::location.location', ({ strapi }) => ({
  /**
   * Bulk upsert controller for POST calls to /locations 
   * Body must be {"data": [locations]} where locations are json objects of the data to be upserted
   * If new you want new locations created to have a specific type, for QA, filtering, etc add the 
   * filed "options" to the body with {"newType"}
   * @param ctx 
   * @returns HTTP Response with errors json for any locations that could not be udated or created
   */
  async bulkUpsert(ctx) {
    try {
      const { data, options } = ctx?.request?.body;
      if (!Array.isArray(data)) {
        return ctx.badRequest('Data must be an array');
      }
      const errors = [];
      await strapi.db.transaction(async () => {
        const locationsMap: IDMap = await strapi
          .service('api::location.location')
          .getLocationMap();

        for (const location of data) {
          const { code, name, ...attributes } = location;

          if (attributes.groups) {
            if (!Array.isArray(attributes.groups)) {
                errors.push({
                  msg: `Invalid groups for location with code ${code}`,
                  err: `Groups must be an array`
                });
                continue
              }
            const [mappedGroups, newErors] = strapi
            .service('api::location.location')
            .mapRelations(attributes.groups, locationsMap);

            attributes.groups = mappedGroups;
            errors.push(...newErors);
          }

          if (attributes.members){
            if (!Array.isArray(attributes.members)) {
                errors.push({
                  msg: `Invalid members for location with code ${code}`,
                  err: `Members must be an array`
                });
                continue
              }
            const [mappedMembers, neweErors] = strapi
            .service('api::location.location')
            .mapRelations(attributes.members, locationsMap);

            attributes.members = mappedMembers;
            errors.push(...neweErors);
          }

          // No existing record, create a new one
          if (!locationsMap[code]) {
            // Defaulting undesignated new locs as territories since they are not
            // shown on the map search. This gives us time to update any needed map layers
            // before we start showing them.
            if (options?.newType) {
              attributes.type = options.newType
            }
            await strapi.entityService.create(
              'api::location.location',
              {
                data: {
                  code,
                  name,
                  ...attributes,
                },
              }
            );
          } else {
            // Existing record, update it
            await strapi.entityService.update(
              'api::location.location',
              locationsMap[code],
              {
                data: {
                  ...attributes,
                },
              }
            );
          }
        }
      }
      );
      return ctx.send({ message: 'Locations upserted successfully', errors });
    } catch (error) {
      strapi.log.error('Error in locations bulkUpsert:', {error: error?.message });
      return ctx.internalServerError('An error occurred while upserting locations', error);
    }
  }
}));
