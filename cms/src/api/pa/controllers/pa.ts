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
  async bulkUpsert(ctx) {
    // console.log("Context", ctx, ctx.request.body);
    if (!Array.isArray(ctx?.request?.body?.data)) {
      return ctx.badRequest('Invalid data format. Expected a body with an array of objects.');
    }
    const errors = []
    const data = ctx.request.body.data;
    for (const item of data) {
      const { id, wdpaid, zone, ...attributes } = item;
      if (id) {
        // Update existing entry
        await strapi.entityService.update('api::pa.pa', id, {
          data: attributes,
        });
      }
      else {
        console.log("wdpaid", wdpaid);
        const filters = {
          ...(wdpaid && { wdpaid }), 
          ...(zone && { zone })
        };
        console.log("filters", filters);
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
            strapi.log.warn('Multiple entries found for PA upsert', {wdpaid, zone, name: attributes?.name});
          }
          errors.push({wdpaid, zone, name: attributes?.name, message: 'Multiple entries found with the same wdpaid, zone, and/or name.'});
        } else {
          // Create new entry
          await strapi.entityService.create('api::pa.pa', {
            data: {
              ...attributes,
              ...(wdpaid && { wdpaid }),
              ...(zone && { zone })
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
    ...(errors.length > 0 && errors) ,
  });
  }
}));
