/**
 * pa service
 */

import { factories } from '@strapi/strapi';

import type { ApiPaPa } from '@/types/generated/contentTypes';
import type { Shared } from '@strapi/strapi';

export default factories.createCoreService('api::pa.pa', ({ strapi }) => ({
  async updateWithRelations(pa, trx = null) {
    try {
      const connection = trx ?? strapi.db.connection;
      // const {
      //   child,
      //   data_source,
      //   environment,
      //   protection_status,
      //   iucn_category,
      //   location,
      //   mpaa_protection_level,
      //   mpaa_establishment_stage,
      //   id,
      //   parent,
      //   ...attributes
      // } = pa;
      const {
        id,
        year,
        name,
        area,
        bbox,
        wdpaid,
        wdpa_p_id,
        zone_id,
        coverage
      } = pa;

      const attributes = {
        year,
        name,
        area,
        bbox,
        wdpaid,
        wdpa_p_id,
        zone_id,
        coverage
      }

      const linkedFields = [
        "children",
        "data_source", 
        "environment",
        "protection_status",
        "iucn_category",
        "location",
        "mpaa_protection_level",
        "mpaa_stablishment_stage",
        "parent",
      ];

      const res = await connection('pas').where({ id }).update(attributes, ['id']);
      // Continue with falsy values other than undefined which are used to unset the realtionship
        for (const field of linkedFields) {
          if (pa[field] !== undefined) {
            await this.updateLinkTable(field, id, pa[field], connection)
          }
        }
      return res[0];
    } catch (error) {
      strapi.log.error('Error in PA updateWithRelations: ', error);

    }
  },
  async updateLinkTable(field, pa_id, linkID, connection) {
    const linkTable = `pas_${field}_links`; 
    const linkIDName = field ===  'parent' || field === 'children' 
      ? 'inv_pa_id'
      : `${field}_id`;
     console.log("Here we update " + linkTable, pa_id, linkID)
     await connection(linkTable).where({ pa_id }).del();
     if (Array.isArray(linkID)) {
      //  for (const id of linkID) { 
      for (let i=0; i<linkID.length; i++) {
        const id = +linkID[i];
        await connection(linkTable).insert({ pa_id, [linkIDName]: id })
      }
     } else if (linkID) {
      await connection(linkTable).insert({ pa_id, [linkIDName]: linkID })
    }
  },

  async getRelations(pa: ApiPaPa['attributes']) {
    type ContentTypeKey = keyof Shared.ContentTypes
    type ApiSuffix<S extends String> =
      S extends `api::${infer Rest}` ? Rest : never
    type ValidSuffix = ApiSuffix<ContentTypeKey>


    // const relations = {};
    // const relationFields: {[key: String] : ValidSuffix} = {
    //     protection_status: 'protection-status',
    //     children: 'pas',
    //     parent: 'pas',
    //     data_source: 'data-source',
    //     mpaa_establishment_stage: 'mpaa_establishment_stage' ,
    //     location: 'location',
    //     mpaa_protection_level: 'mpaa_protection_level',
    //     iucn_category: 'iucn_category',
    //     environment:'environment'
    // };

    // for (const attr in pa) {
    //   if (relationFields[attr]) {
    //      // @ts-ignore
    //     const contentType: `api::${ValidSuffix}` = `api::${relationFields[attr]}:${relationFields[attr]}`;
    //     const id = await strapi.entityService?.findMany(contentType,
    //      { 
    //       filters: {
    //         slug: pa[attr] 
    //       }
    //     })
    //   }
    // }
  },
}));
