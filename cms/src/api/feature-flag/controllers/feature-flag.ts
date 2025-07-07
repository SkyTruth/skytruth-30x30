/**
 * feature-flag controller
 */

import { factories } from '@strapi/strapi'

export default factories.createCoreController('api::feature-flag.feature-flag',
  ({ strapi }) => ({
    async find(ctx) {
      const { query, request: {header} } = ctx
      console.log(query, ctx.query, header)
      const data = await super.find(ctx);
      console.log("DATA", data)
      return data;
    }
  })
);
