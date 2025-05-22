/**
 * pa service
 */

import { factories } from '@strapi/strapi';

import type { ApiPaPa } from '@/types/generated/contentTypes';
import type { Shared } from '@strapi/strapi';

export default factories.createCoreService('api::pa.pa', ({ strapi }) => ({
  async getRelations(pa: ApiPaPa['attributes']) {
    type ContentTypeKey = keyof Shared.ContentTypes
    type ApiSuffix<S extends String> =
      S extends `api::${infer Rest}` ? Rest : never
    type ValidSuffix = ApiSuffix<ContentTypeKey>


    const relations = {};
    const relationFields: {[key: String] : ValidSuffix} = {
        protection_status: 'protection-status',
        children: 'pas',
        parent: 'pas',
        data_source: 'data-source',
        mpaa_establishment_stage: 'mpaa_establishment_stage' ,
        location: 'location',
        mpaa_protection_level: 'mpaa_protection_level',
        iucn_category: 'iucn_category',
        environment:'environment'
    };

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
