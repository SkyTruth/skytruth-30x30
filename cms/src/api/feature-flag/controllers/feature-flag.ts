/**
 * feature-flag controller
 */

import { factories } from '@strapi/strapi'

export default factories.createCoreController('api::feature-flag.feature-flag',
  ({ strapi }) => ({
    async find(ctx) {
      const { query, request: { header } } = ctx

      const runAsOf = header['run-as-of'] ? new Date(header['run-as-of']) 
        : query.runAsOf ? new Date(query.runAsOf) : new Date();
      console.log(query, ctx.query, header);
      // This internal endpoint will only return the payload of the feature flag. 
      // Getting all fields here ensure's we have access to the aactive_at date
      query.fields = '*';
    
      console.log("Query", ctx. query);
      const data = await super.find(ctx);
      console.log('return features', data);
      const validatedFeatureFlags = strapi.services['api::feature-flag.feature-flag']
        .validateFeatureFlags(data.data, runAsOf);
      console.log("DATA", validatedFeatureFlags)
      const formattedResponse = validatedFeatureFlags.map(({ attributes: { payload, feature } } )=> {
      return {
        feature,
        payload
      };
    });

      return ctx.send(formattedResponse)
    }
  })
);
