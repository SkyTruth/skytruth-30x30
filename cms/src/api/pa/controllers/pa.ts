/**
 * pa controller
 */

import { factories } from '@strapi/strapi'

import filterSovereigns from '../../../utils/filter-sovereigns';

export default factories.createCoreController('api::pa.pa', ({ strapi }) => ({
  async find(ctx) {
    // TODO TECH-3174: Clean up
    const { query } = ctx;
    let locationFilter = query?.filters?.location;
    const areTerritoriesActive = await strapi
        .service('api::feature-flag.feature-flag')
        .getFeaureFlag(ctx, 'are_territories_active');

    if (locationFilter && !areTerritoriesActive) {
        query.filters.location = filterSovereigns({...locationFilter})
    }
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
          message: created.length + ' Entries created successfully.',
          created,
          errors
        });
    } catch (error) {
        strapi.log.error('Error in PAS bulkInsert:', error);
      return ctx.internalServerError('An error occurred while processing the request.', { error });
      }
  },
  async bulkPatch(ctx) {
    /**
     * Currently this endpoint only accepts DELETE as a method, all other methods will return a 
     * 400 status
     */
    try {
      if (!ctx?.request?.body?.data?.method || !ctx?.request?.body?.data?.ids) {
          return ctx.badRequest('Invalid data format. Expected a body with a "method" key and an "ids" array.');
        }
      if (ctx.request.body.data.method !== 'DELETE') {
        return ctx.badRequest('Invalid method. Only DELETE is supported for bulk patch.');
      }
      const ids = ctx.request.body.data.ids; 
      const knex = strapi.db.connection;
      const errors = [];
      const deleted = [];

      await knex.transaction(async (trx) => {
        for (const id of ids) {
          const deleteResponse = await trx('pas').where({ id }).delete(['id']);
          if (!deleteResponse || deleteResponse.length === 0) {
            errors.push({msg: "Failed to delete PA with ID " + id });
          } else {
            deleted.push(deleteResponse[0].id)
          }
        }
      });
      return ctx.send({
          message: deleted.length + ' Entries updated successfully.',
          deleted,
          errors
        });

    } catch (error) {
      strapi.log.error('Error in PAS bulkDelete:', error);
      return ctx.internalServerError('An error occurred while processing the request.', { error });
    }

  }
}));
