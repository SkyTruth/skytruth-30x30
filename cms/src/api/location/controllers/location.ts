/**
 * location controller
 */

import { factories } from '@strapi/strapi'

export default factories.createCoreController('api::location.location', ({ strapi }) => ({
  async bulkUpsert(ctx) {
    try {
      const { data } = ctx?.request?.body;
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

          if (attributes.groups){
            if (!Array.isArray(attributes.groups)) {
                errors.push({
                  msg: `Invalid groups for location with code ${code}`,
                  err: `Groups must be an array`
                });
                continue
              }
            const [mappedGroups, neweErors] = strapi
            .service('api::location.location')
            .mapRelations(attributes.groups, locationsMap);

            attributes.groups = mappedGroups;
            errors.push(...neweErors);
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
            if (!attributes.type) {
              attributes.type = 'territory'
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
      console.error('Error in bulkUpsert:', error);
      return ctx.internalServerError('An error occurred while upserting locations', error);
    }
  }
}));
