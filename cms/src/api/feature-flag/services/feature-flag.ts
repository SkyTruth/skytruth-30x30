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
})
);
