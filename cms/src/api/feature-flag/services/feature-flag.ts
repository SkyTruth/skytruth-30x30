/**
 * feature-flag service
 */

import { factories } from '@strapi/strapi';
import { ApiFeatureFlagFeatureFlag } from '@/types/generated/contentTypes';

export default factories.createCoreService('api::feature-flag.feature-flag', () => ({
  validateFeatureFlags(featureFlags: Array<ApiFeatureFlagFeatureFlag['attributes']>, runAsOf: Date):
    Array<ApiFeatureFlagFeatureFlag['attributes']> {
      const validFeatureFlags = featureFlags.filter(flag => {

      if (flag.archived) {
        return false;
      }

      if (!flag.active_on || 
        (flag.active_on && new Date(flag.active_on.toString()) <= runAsOf)
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

    const flags =  await strapi.documents('api::feature-flag.feature-flag').findMany({
        filters: {
            feature: {
                '$eq': name
            }
        },
    })

    // Reusing logic that expects the api formatted response so coerse the response to match
    const validatedFeatureFlags = strapi
      .services['api::feature-flag.feature-flag']
      .validateFeatureFlags(flags, formattedRunAsOf);

    return validatedFeatureFlags[0];
  }
}));
