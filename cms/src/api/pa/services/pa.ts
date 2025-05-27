/**
 * pa service
 */

import { factories } from '@strapi/strapi';

type PA = {
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
  mpaa_stablishment_stage?: number | null;
  parent?: number | null;
};

export default factories.createCoreService('api::pa.pa', ({ strapi }) => ({
  async upsertWithRelations(pa: PA, trx: typeof strapi.db.connection = null):
    Promise<{ id: number | null; error: Error | null }> {
    try {
      const connection = trx ?? strapi.db.connection;
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
        bbox: bbox ? JSON.stringify(bbox) : bbox,
        wdpaid,
        wdpa_p_id,
        zone_id,
        coverage
      }

      const linkedFields: string[] = [
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

      let res: PA[] = [];
      if (id) {
       res = await connection('pas').where({ id }).update(attributes, ['id']);
      } else {
        res = await connection('pas').insert(attributes, ['id']);
      }
      // Continue with falsy values other than undefined which are used to unset the realtionship
        for (const field of linkedFields) {
          console.log(field)
          if (pa[field] !== undefined) {
            await this.insertLinkTable(field, res[0].id, pa[field], connection)
          }
        }
      return {
        id: res[0].id,
        error: null
      }
    } catch (error) {
      strapi.log.error('Error in PA upsertWithRelations: ', error);
      return {
        id: null,
        error
      }
    }
  },
  async insertLinkTable(
    field: string,
    pa_id: number,
    linkID: number | number[],
    connection: typeof strapi.db.connection): 
      Promise<void> {
    const linkTable: string = `pas_${field}_links`; 
    let linkIDName: string;

      switch (field) {
        case 'children':
        case 'parent':
          linkIDName = 'inv_pa_id';
          break;
        case 'iucn_category':
          linkIDName = 'mpa_iucn_category_id';
          break;
        default:
          linkIDName = `${field}_id`;
          break;
      }
     await connection(linkTable).where({ pa_id }).del();
     if (Array.isArray(linkID)) {
      for (let i=0; i<linkID.length; i++) {
        const id = +linkID[i];
        await connection(linkTable).insert({ pa_id, [linkIDName]: id })
      }
     } else if (linkID) {
      await connection(linkTable).insert({ pa_id, [linkIDName]: linkID })
    }
  },
}));
