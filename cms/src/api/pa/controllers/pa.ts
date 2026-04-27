/**
 * pa controller
 */

import { factories } from '@strapi/strapi'

export type PARelations = {
  documentId?: string;
  wdpaid?: number;
  wdpa_p_id?: string;
  zone_id?: number;
  environment?: string;
  location?: string;
  key?: string;
}

export type ToUpdateRelations = {
  documentId?: {
    children: PARelations[]
    parent: PARelations
  }
}

export type PA = {
  documentId?: string;
  year?: number;
  name?: string;
  area?: number;
  bbox?: number[] | null;
  wdpaid?: number | null;
  wdpa_p_id?: string | null;
  zone_id?: number | null;
  coverage?: number | null;
  children?: string[] | null;
  data_source?: string | null;
  environment?: string | null;
  protection_status?: string | null;
  iucn_category?: string | null;
  location?: string | null;
  mpaa_protection_level?: string | null;
  mpaa_establishment_stage?: string | null;
  parent?: string | null;
  created_at?: Date;
  updated_at?: Date;
};

export type InputPA = {
  parent: PARelations,
  children: PARelations[],
} & PA

/**
 * Build a relation payload for a localized (i18n-enabled) target content type.
 * Strapi v5 (5.38) does not reliably honor the documented "default locale" fallback
 * when a bare documentId string is passed as a relation value — the link table can
 * end up pointing at an arbitrary locale variant. Passing { documentId, locale }
 * explicitly pins the link to the English row. Returns null for a falsy input so
 * optional relations remain unset.
 */
const toLocalizedRelation = (map: IDMap, value: string) => {
  if (!value) return null;
  return { documentId: map[value], locale: 'en' };
};


export default factories.createCoreController('api::pa.pa', ({ strapi }) => ({
  async find(ctx) {
    if (ctx.query['keep-if-children-match']) {
      // In addition to the controller's default behavior, we also want to keep the rows for which
      // there is at least one child that matches the filters. For this, we'll use the `children`
      // and `parent` fields.

      // First, we get the list of all the parents (no pagination) for which at least one child
      // matches the filters. No sorting.
      
      // @ts-ignore
      const { parent, ...filtersWithoutParentProperty } = (ctx.query.filters ?? {});

      const parentIds = (await strapi.documents('api::pa.pa').findMany({
        fields: ['documentId'],
        populate: {
          parent: {
            fields: ['documentId'],
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
      }) as { documentId: string; parent: { documentId: string } }[]).map((d) => d.parent.documentId);

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
                    documentId: {
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

          const updatedPA = strapi.service('api::pa.pa')
            .checkParentChild(pa, toUpdateRelations)
          const {
            documentId,
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
          if (documentId) {
            await strapi.documents("api::pa.pa").update({
              documentId: documentId,
              data: {
                data_source: toLocalizedRelation(dataSourceMap, data_source),
                environment: toLocalizedRelation(environmentMap, environment),
                location: locationMap[location],
                iucn_category: toLocalizedRelation(mpaaIucnCategoryMap, iucn_category),
                mpaa_establishment_stage: toLocalizedRelation(
                  mpaaEstablishmentStageMap, mpaa_establishment_stage
                ),
                mpaa_protection_level: toLocalizedRelation(
                  mpaaProtectionLevelMap, mpaa_protection_level
                ),
                protection_status: toLocalizedRelation(protectionStatusMap, protection_status),
                ...attributes
              }
            })
            updated++;
          // No database ID so create a new record
          } else {
            //Break the required fields out just to keep the type checker happy
            const { name, area, bbox, coverage, ...optionalAttributes } = attributes;
            const newPA = await strapi.documents("api::pa.pa").create({
              data: {
                area,
                bbox,
                coverage,
                name,
                data_source: toLocalizedRelation(dataSourceMap, data_source),
                environment: toLocalizedRelation(environmentMap, environment),
                location: locationMap[location],
                iucn_category: toLocalizedRelation(mpaaIucnCategoryMap, iucn_category),
                mpaa_establishment_stage: toLocalizedRelation(
                  mpaaEstablishmentStageMap, mpaa_establishment_stage
                ),
                mpaa_protection_level: toLocalizedRelation(
                  mpaaProtectionLevelMap, mpaa_protection_level
                ),
                protection_status: toLocalizedRelation(protectionStatusMap, protection_status),
                ...optionalAttributes
              }
            })
            
            /**
             * Make the identifier key with the original data because the create method doesn't
             * return relational fields
             */ 
            const paKey = strapi.service('api::pa.pa').makePAKey(updatedPA);
            newIdMap[paKey] = newPA.documentId;

            /**
             * If the newly created Pa has relations to update later add its 
             * new ID update relations map
             */
            if (toUpdateRelations[paKey]) {
              toUpdateRelations[newPA.documentId] = toUpdateRelations[paKey];
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

        const children = relations?.children?.map(child => child?.documentId ? 
          child.documentId : 
          newIdMap[child.key])
        
        const parent = relations?.parent?.key ? newIdMap[relations.parent.key] : null;

        await strapi.documents('api::pa.pa').update({
          documentId: toUpdate,
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
      const errors = [];
      const deleted = [];

      await strapi.db.transaction(async () => {
        for (const documentId of ids) {
          try {
            await strapi.documents('api::pa.pa').delete({
              documentId: documentId,
            });
            deleted.push(documentId);
          } catch (error) {
            errors.push({ msg: `Failed to delete PA with documentId ${documentId}`, error: error.message });
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
