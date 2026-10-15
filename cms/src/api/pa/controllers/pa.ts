/**
 * pa controller
 */

import { factories } from '@strapi/strapi'

export type RowIdMap = {
  [key: string]: number;
}

export type PARelations = {
  id?: number;
  wdpaid?: number;
  wdpa_p_id?: string;
  zone_id?: number;
  environment?: string;
  location?: string;
  key?: string;
}

export type ToUpdateRelations = {
  [paIdentifier: string]: {
    children?: PARelations[]
    parent?: PARelations
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
  data_source?: string | null;
  environment?: string | null;
  protection_status?: string | null;
  iucn_category?: string | null;
  location?: string | null;
  mpaa_protection_level?: string | null;
  mpaa_establishment_stage?: string | null;
  parent?: number | null;
  created_at?: Date;
  updated_at?: Date;
};

export type InputPA = {
  parent: PARelations,
  children: PARelations[],
} & PA

const toRelationId = (map: RowIdMap, value: string) => (value ? map[value] : null);

const isOptionalInteger = (value: unknown) => value == null || Number.isInteger(value);

const hasIntegerIds = (pa: InputPA) =>
  isOptionalInteger(pa?.id) &&
  isOptionalInteger(pa?.parent?.id) &&
  (pa?.children ?? []).every((child) => isOptionalInteger(child?.id));

const getRelatedIds = (pa: InputPA) =>
  [pa?.parent?.id, ...(pa?.children ?? []).map((child) => child?.id)].filter((id) => id != null);

// A link to a missing PA fails the link table's foreign key and rolls back the whole request.
const dropMissingRelations = (
  pa: InputPA,
  existingIds: Set<number>,
  errors: {msg: string, err: string}[]
) => {
  if (pa?.parent?.id != null && !existingIds.has(pa.parent.id)) {
    errors.push({
      msg: `Dropped parent of PA, name: ${pa?.name}`,
      err: `No PA found with id ${pa.parent.id}`
    });
    delete pa.parent;
  }
  if (pa?.children) {
    const missingChildren = pa.children.filter(
      (child) => child?.id != null && !existingIds.has(child.id)
    );
    missingChildren.forEach((child) => {
      errors.push({
        msg: `Dropped child of PA, name: ${pa?.name}`,
        err: `No PA found with id ${child.id}`
      });
      pa.children.splice(pa.children.indexOf(child), 1);
    });
  }
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
      if (!data.every(hasIntegerIds)) {
        return ctx.badRequest('Invalid ids. Expected integer ids for PAs, parents, and children.');
      }
      const idMaps = await strapi.service('api::pa.pa').getRelationIdMaps()
      const {
        dataSourceMap,
        environmentMap,
        locationMap,
        mpaaEstablishmentStageMap, 
        mpaaIucnCategoryMap,
        mpaaProtectionLevelMap,
        protectionStatusMap,
      } = idMaps;

      const relatedIds = data.flatMap(getRelatedIds);
      const existingRelatedRows = relatedIds.length
        ? await strapi.db.query('api::pa.pa').findMany({
          select: ['id'],
          where: { id: { $in: relatedIds } },
        })
        : [];
      const existingIds = new Set<number>(existingRelatedRows.map((row) => row.id));

      let updated = 0;
      let created = 0;

      const errors: {msg: string, err: string}[] = [];
      const toUpdateRelations: ToUpdateRelations = {};
      const newIdMap: RowIdMap = {};
      const publishedAt = new Date();

      // Query Engine, not Document Service: the latter queues a fully populated lookup per row
      // after commit, which exhausts the connection pool on large upserts.
      await strapi.db.transaction(async () => {
        for (const pa of data) {
          const areRelationsValid = strapi.service('api::pa.pa')
            .validateFields(pa, idMaps, errors);
          
          if (!areRelationsValid) {
            continue;
          }

          dropMissingRelations(pa, existingIds, errors);

          const updatedPA = strapi.service('api::pa.pa')
            .checkParentChild(pa, toUpdateRelations)
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

          const paData = {
            data_source: toRelationId(dataSourceMap, data_source),
            environment: toRelationId(environmentMap, environment),
            location: toRelationId(locationMap, location),
            iucn_category: toRelationId(mpaaIucnCategoryMap, iucn_category),
            mpaa_establishment_stage: toRelationId(
              mpaaEstablishmentStageMap, mpaa_establishment_stage
            ),
            mpaa_protection_level: toRelationId(mpaaProtectionLevelMap, mpaa_protection_level),
            protection_status: toRelationId(protectionStatusMap, protection_status),
            publishedAt,
            ...attributes
          };

          // Record exists, update in place
          if (id) {
            const updatedRow = await strapi.db.query('api::pa.pa').update({
              where: { id },
              data: paData,
              select: ['id'],
            });
            if (!updatedRow) {
              errors.push({
                msg: `Failed to update PA, name: ${pa?.name}, id: ${id}`,
                err: 'No PA found with this id; its parent/child relations were not updated'
              });
              delete toUpdateRelations[id];
              continue;
            }
            updated++;
          // No database ID so create a new record
          } else {
            const newPA = await strapi.db.query('api::pa.pa').create({
              data: paData,
              select: ['id'],
            });
            
            /**
             * Make the identifier key with the original data because the create method doesn't
             * return relational fields
             */ 
            const paKey = strapi.service('api::pa.pa').makePAKey(updatedPA);
            newIdMap[paKey] = newPA.id;

            /**
             * If the newly created Pa has relations to update later add its 
             * new ID update relations map
             */
            if (toUpdateRelations[paKey]) {
              toUpdateRelations[newPA.id] = toUpdateRelations[paKey];
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

        const children = relations?.children?.map(child => child?.id ?? newIdMap[child.key])
        
        const parent = relations?.parent?.key ? newIdMap[relations.parent.key] : null;

        await strapi.db.query('api::pa.pa').update({
          where: { id: Number(toUpdate) },
          data: {
            ...(children ? { children } : {}),
            ...(parent ? { parent } : null)
          },
          select: ['id'],
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
