/**
 * feature-flag controller
 */

import { factories } from '@strapi/strapi'

export default factories.createCoreController('api::feature-flag.feature-flag',
  ({ strapi }) => ({
    async find(ctx) {
      try {
      const { query, request: { header } } = ctx;

      // User defined runAsOf date preferentailly uses the header, then query, then defaults to now
      const runAsOf = header['run-as-of'] ? new Date(header['run-as-of']) 
        : query['run-as-of'] ? new Date(query['run-as-of']) : new Date();

      // Getting all fields here ensures we have access to the active_at date
      query.fields = '*';
    
      const data = await super.find(ctx);

      const validatedFeatureFlags = strapi.services['api::feature-flag.feature-flag']
        .validateFeatureFlags(data.data, runAsOf);

      return ctx.send(validatedFeatureFlags)
    } catch (error) {
        strapi.log.error('Error in feature-flag controller find:', error);
        return ctx.badRequest('Failed to retrieve feature flags', { error: error.message });
    }
    }
  })
);
