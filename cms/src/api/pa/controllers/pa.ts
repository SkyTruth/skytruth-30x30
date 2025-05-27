/**
 * pa controller
 */

import { factories } from '@strapi/strapi'

export default factories.createCoreController('api::pa.pa', ({ strapi }) => ({
  async find(ctx) {
    if (ctx.query['keep-if-children-match']) {
      // In addition to the controller's default behavior, we also want to keep the rows for which
      // there is at least one child that matches the filters. For this, we'll use the `children`
      // and `parent` fields.

      // First, we get the list of all the parents (no pagination) for which at least one child
      // matches the filters. No sorting.
      const { parent, ...filtersWithoutParentProperty } = ctx.query.filters ?? {};

      const parentIds = (await strapi.entityService.findMany('api::pa.pa', {
        fields: ['id'],
        populate: {
          parent: {
            fields: ['id'],
          },
        },
        filters: {
          $and: [
            {
              parent: {
                name: {
                  $null: false,
                },
              },
            },
            filtersWithoutParentProperty,
          ],
        },
        limit: -1,
      }) as { id: number; parent: { id: number } }[]).map((d) => d.parent.id);

      const uniqueParentIds = [...new Set(parentIds)];

      // Then, we get the list of all parents that match the initial request or the ones for which
      // children match, using the list of ids `uniqueParentIds`.
      return await super.find({
        ...ctx,
        query: {
          ...ctx.query,
          filters: {
            $and: [
              {
                parent: {
                  name: {
                    $null: true,
                  },
                },
              },
              {
                $or: [
                  filtersWithoutParentProperty,
                  {
                    id: {
                      $in: uniqueParentIds,
                    },
                  },
                ],
              },
            ],
          }
        },
      });
    } else {
      return await super.find(ctx);
    }
  },
  async bulkUpdate(ctx) {
    try {
      if (!Array.isArray(ctx?.request?.body?.data)) {
        return ctx.badRequest('Invalid data format. Expected a body with an array of objects.');
      }
      const data = ctx.request.body.data;
      const knex = strapi.db.connection;
      const errors = [];
      const updated = []
      await knex.transaction(async (trx) => {
        for (const pa of data) {
          if (!pa.id) {
            errors.push({ name: pa?.name, msg: "Missing PA ID"});
          }
          const updateResponse = await strapi.service('api::pa.pa').upsertWithRelations(pa, trx);
          if (updateResponse.error) {
            errors.push({ name: pa?.name, msg: "Failed to update PA with ID " + pa.id + ": " + updateResponse.error });
          } else {
            updated.push(updateResponse.id)
          }
        }
      })
      return ctx.send({
          message: updated.length + ' Entries updated successfully.',
          updated,
          errors
        });
    } catch (error) {
      strapi.log.error('Error in PAS bulkUpdate:', error);
      return ctx.internalServerError('An error occurred while processing the request.', { error });
    }
  },
  async bulkInsert(ctx) {
    try {
      if (!Array.isArray(ctx?.request?.body?.data)) {
        return ctx.badRequest('Invalid data format. Expected a body with an array of objects.');
      }
      const data = ctx.request.body.data;
      const knex = strapi.db.connection;
      const errors = [];
      const created = []

      await knex.transaction(async (trx) => {
        for (const pa of data) {
          const updateResponse = await strapi.service('api::pa.pa').upsertWithRelations(pa, trx);
          if (updateResponse.error) {
            errors.push({ name: pa?.name, msg: "Failed to update PA with ID " + pa.id + ": " + updateResponse.error });
          } else {
            created.push(updateResponse.id)
          }
        }
      });
      return ctx.send({
          message: created.length + ' Entries updated successfully.',
          created,
          errors
        });
    } catch (error) {
        strapi.log.error('Error in PAS bulkInsert:', error);
      return ctx.internalServerError('An error occurred while processing the request.', { error });
      }
  },
  async bulkUpsert(ctx) {
    console.log("not here right")
    // console.log("Context", ctx, ctx.request.body);
    try{
      if (!Array.isArray(ctx?.request?.body?.data)) {
        return ctx.badRequest('Invalid data format. Expected a body with an array of objects.');
      }
      const knex = strapi.db.connection;
      await knex.transaction(async (trx) => {

        const errors = []
      
        const data = ctx.request.body.data;
        for (const item of data) {
          const { id, wdpaid, zone_id, ...attributes } = item;
          if (id) {
            // Update existing entry
            await strapi.entityService.update('api::pa.pa', id, {
              data: attributes,
            });
          }
          else {
            const filters = {
              ...(wdpaid && { wdpaid }), 
              ...(zone_id && { zone_id })
            };
            const entries = await strapi.entityService.findMany('api::pa.pa', 
              {
              fields: ['name'],
              filters,
              }
            )
            console.log(entries)
            if (entries.length === 1) {
              // Entry already exists, update it
              await strapi.entityService.update('api::pa.pa', entries[0].id, {
                data: attributes,
              });
            } else if (entries.length > 1) {
              // Handle the case where multiple entries are found
              let record = null;
              if (attributes?.name) {
                record = entries.find((entry) => entry.name === attributes.name)
              }
              if (!attributes?.name || !record) {
                strapi.log.warn('Multiple entries found for PA upsert', {wdpaid, zone_id, name: attributes?.name});
              }
              errors.push({wdpaid, zone_id, name: attributes?.name, message: 'Multiple entries found with the same wdpaid, zone_id, and/or name.'});
            } else {
              // Create new entry
              await strapi.entityService.create('api::pa.pa', {
                data: {
                  ...attributes,
                  ...(wdpaid && { wdpaid }),
                  ...(zone_id && { zone_id })
                },
              });
            }
          }
        }

        if (errors.length === ctx.request.body.data.length) {
          // All entries failed to create or update
          return ctx.badRequest('Some entries were not created or updated.', { errors });
        }
        return ctx.send({
          message: 'Entries created or updated successfully.',
          errors: errors.length > 0 ? errors : null
        });
      })
    } catch (error) {
      strapi.log.error('Error in bulkUpsert:', error);
      return ctx.internalServerError('An error occurred while processing the request.', { error });
    }
  }
}));
