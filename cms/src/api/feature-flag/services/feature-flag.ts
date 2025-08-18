/**
 * feature-flag service
 */

import { factories } from '@strapi/strapi';
import { ApiFeatureFlagFeatureFlag } from '@/types/generated/contentTypes';

export default factories.createCoreService('api::feature-flag.feature-flag', () => ({
  validateFeatureFlags(featureFlags: Array<ApiFeatureFlagFeatureFlag>, runAsOf: Date):
    Array<ApiFeatureFlagFeatureFlag> {
      const validFeatureFlags = featureFlags.filter(flag => {
        const { attributes } = flag;

      if (attributes.archived) {
        return false;
      }

      if (!attributes.active_on || 
        (attributes.active_on && new Date(attributes.active_on.toString()) <= runAsOf)
      ) {
        return true;
      }

      return false;

    });
    return validFeatureFlags

  },
  async getFeaureFlag(ctx, name) {
    /**
     * Helper service to extract single feature flag on the backend
     */
    const { query, request: { header } } = ctx;
    const runAsOf = header['run-as-of'] ?? query['run-as-of']
    const formattedRunAsOf = runAsOf ? new Date(runAsOf) : new Date()

    const flags =  await strapi.entityService.findMany('api::feature-flag.feature-flag', {
        filters: {
            feature: {
                '$eq': name
            }
        },
    })

    // Reusing logic that expects the api formatted response so coerse the response to match
    const formattedFlags = flags.map(flag => { return { attributes: flag } })
    const validatedFeatureFlags = strapi
      .services['api::feature-flag.feature-flag']
      .validateFeatureFlags(formattedFlags, formattedRunAsOf);
        

    return validatedFeatureFlags[0];
  }
}));
