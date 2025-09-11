/**
 * pa controller
 */

import { factories } from '@strapi/strapi'

import filterSovereigns from '../../../utils/filter-sovereigns';

export type PARelations = {
  id?: number,
  wdpaid?: number,
  wdpa_p_id?: string,
  zone_id?: number,
  environment?: string,
  key?: string
}

export type ToUpdateRelations = {
  id?: {
    children: PARelations[]
    parent: PARelations
  }
}

export type PA = {
  id?: number;
  year?: number;
  name?: string;
  area?: number;
  bbox?: number[] | null;
  wdpaid?: number | null;
  wdpa_p_id?: string | null;
  zone_id?: number | null;
  coverage?: number | null;
  children?: number[] | null;
  data_source?: number | null;
  environment?: number | null;
  protection_status?: number | null;
  iucn_category?: number | null;
  location?: number | null;
  mpaa_protection_level?: number | null;
  mpaa_establishment_stage?: number | null;
  parent?: number | null;
  created_at?: Date;
  updated_at?: Date;
};

export type InputPA = {
  parent: PARelations,
  children: PARelations[],
} & PA


export default factories.createCoreController('api::pa.pa', ({ strapi }) => ({
  async find(ctx) {
    // TODO TECH-3174: Clean up
    const { query } = ctx;
    let locationFilter = query?.filters?.location;
    let childLocationFilters = query?.populate?.children?.filters?.location;
    const areTerritoriesActive = await strapi
        .service('api::feature-flag.feature-flag')
        .getFeaureFlag(ctx, 'are_territories_active');

    if (locationFilter && !areTerritoriesActive) {
        query.filters.location = filterSovereigns({...locationFilter});
    }

    if (childLocationFilters && !areTerritoriesActive) {
        query.populate.children.filters.location = filterSovereigns({...childLocationFilters})
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
  async bulkUpsert(ctx) {
    try {
      const { data }: {data: InputPA[]} = ctx?.request?.body;
      if (!Array.isArray(data)) {
        return ctx.badRequest('Invalid data format. Expected a body with an array of objects.');
      }
      const idMaps = await strapi.service('api::pa.pa').getRelationMaps()
      const {
        dataSourceMap,
        environmentMap,
        locationMap,
        mpaaEstablishmentStageMap, 
        mpaaIucnCategoryMap,
        mpaaProtectionLevelMap,
        protectionStatusMap,
      } = idMaps;
  
      let updated = 0;
      let created = 0;

      const errors: {msg: string, err: string}[] = [];
      const toUpdateRelations: ToUpdateRelations = {};
      const newIdMap: IDMap = {};

      await strapi.db.transaction(async () => {
        for (const pa of data) {

          const areRelationsValid = strapi.service('api::pa.pa')
            .validateFields(pa, idMaps, errors);
          
          if (!areRelationsValid) {
            continue;
          }

          const updatedPA = strapi.service('api::pa.pa').checkParentChild(pa, toUpdateRelations, newIdMap)
          const {
            id,
            data_source,
            environment,
            location,
            iucn_category,
            mpaa_establishment_stage,
            mpaa_protection_level,
            protection_status,
            ...attributes
          } = updatedPA as PA;

          // Record exists, update in place
          if (id) {
            await strapi.entityService.update("api::pa.pa", id, {
              data: {
                data_source: dataSourceMap[data_source],
                environment: environmentMap[environment],
                location: locationMap[location],
                iucn_category: iucn_category ? mpaaIucnCategoryMap[iucn_category] : iucn_category,
                mpaa_establishment_stage: mpaa_establishment_stage ?
                  mpaaEstablishmentStageMap[mpaa_establishment_stage]: mpaa_establishment_stage,
                mpaa_protection_level: mpaa_protection_level ?
                  mpaaProtectionLevelMap[mpaa_protection_level]: mpaa_protection_level,
                protection_status: protectionStatusMap[protection_status],
                ...attributes
              }
            })
            updated++;
          // No database ID so create a new record
          } else {
            //Break the required fields out just to keep the type checker happy
            const { name, area, bbox, coverage, ...optionalAttributes } = attributes;
            const newPA = await strapi.entityService.create("api::pa.pa", {
              data: {
                area,
                bbox,
                coverage,
                name,
                data_source: dataSourceMap[data_source],
                environment: environmentMap[environment],
                location: locationMap[location],
                iucn_category: iucn_category ? mpaaIucnCategoryMap[iucn_category] : iucn_category,
                mpaa_establishment_stage: mpaa_establishment_stage ?
                  mpaaEstablishmentStageMap[mpaa_establishment_stage]: mpaa_establishment_stage,
                mpaa_protection_level: mpaa_protection_level ?
                  mpaaProtectionLevelMap[mpaa_protection_level]: mpaa_protection_level,
                protection_status: protectionStatusMap[protection_status],
                ...optionalAttributes
              }
            })
            
            /**
             * Make the identifier key with the original data because the creat emethod doesn't
             * return relational fields
             */ 
            const paKey = strapi.service('api::pa.pa').makePAKey(updatedPA);
            newIdMap[paKey] = +newPA.id;

            /**
             * If the newly created Pa has relations to update later add its 
             * new ID update relations map
             */
            if (toUpdateRelations[paKey]) {
              toUpdateRelations[+newPA.id] = toUpdateRelations[paKey];
              delete toUpdateRelations[paKey]
            }
            created++;
          }
        }

      /**
       * First pass of PAs updated or created, now update PAs with relationships that didn't
       * exist at the time the PA was handled
       */
      for (const toUpdate in toUpdateRelations) {
        const relations = toUpdateRelations[toUpdate];
        const id = Number.isNaN(+toUpdate) ? newIdMap[toUpdate] : toUpdate;

        const children = relations?.children?.map(child => child?.id ? 
          child.id : 
          newIdMap[child.key])
        
        const parent = relations?.parent?.key ? newIdMap[relations.parent.key] : null;

        await strapi.entityService.update('api::pa.pa', id, {
          data: {
            ...(children ? { children } : {}),
            ...(parent ? { parent } : null)
          }
        })

      }

      return ctx.send({ message: 'PAs updated successfully', created, updated, errors });
      });

    } catch (error) {
      strapi.log.error('Error in PAS bulkupsert:', error);
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
          message: deleted.length + ' Entries deleted successfully.',
          deleted,
          errors
        });

    } catch (error) {
      strapi.log.error('Error in PAS bulkDelete:', error);
      return ctx.internalServerError('An error occurred while processing the request.', { error });
    }

  }
}));
