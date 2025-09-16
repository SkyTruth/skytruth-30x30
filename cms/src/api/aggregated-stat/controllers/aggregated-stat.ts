/**
 * A set of functions called "actions" for `aggregated-stats`
 */
import { PROTECTION_COVERAGE_STAT_NAMESPACE } from "../../protection-coverage-stat/controllers/protection-coverage-stat";

export default {
  async getStats(ctx) {
    try {
      strapi.entityService
      const stat = await strapi.entityService.findMany(PROTECTION_COVERAGE_STAT_NAMESPACE,
        {
          filters: {
            year: 2025,
            location: {
              code: 'GLOB'
            }
          }
        }
      )
      return stat;
    } catch {
      return false
    }
  }

};
