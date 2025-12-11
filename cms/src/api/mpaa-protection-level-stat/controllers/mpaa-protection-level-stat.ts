/**
 * mpaa-protection-level-stat controller
 */

import { factories } from '@strapi/strapi'

export const MPAA_PROTECTION_LEVEL_STATS_NAMESPACE = 'api::mpaa-protection-level-stat.mpaa-protection-level-stat';

export default factories
  .createCoreController(MPAA_PROTECTION_LEVEL_STATS_NAMESPACE, ({ strapi }) => ({
    async bulkUpsert(ctx) {
      try {
        const { data } = ctx.request?.body;
        if (!Array.isArray(data)) {
            return ctx.badRequest('Data must be an array');
        }
        const errors = [];
        let locationMap: IDMap | null = null;
        let MpaaProtectionLevelMap: IDMap | null = null;

        await strapi.db.transaction(async () => {
          const statsMap = await strapi
          .service(MPAA_PROTECTION_LEVEL_STATS_NAMESPACE)
          .getStatsMap();

          for  (const stat of data) {
            const { area, percentage, total_area } = stat;
            const statKey = `${stat.location}-${stat.mpaa_protection_level}`;

            // No existing record, create a new one
            if (!statsMap[statKey]) {
              if (!locationMap) {
                locationMap = await strapi
                  .service('api::location.location')
                  .getLocationMap();
              }
              if (!locationMap[stat.location]) {
                errors.push({
                  msg: `Location ${stat.location} not found`
                });
                continue;
              }
              if (!MpaaProtectionLevelMap) {
                MpaaProtectionLevelMap = await strapi
                  .service('api::mpaa-protection-level.mpaa-protection-level')
                  .getMpaaProtectionLevelMap();
              }
              if (!MpaaProtectionLevelMap[stat.mpaa_protection_level]) {
                errors.push({
                  msg: `MPAA Protection Level ${stat.mpaa_protection_level} not found`
                });
                continue;
              }
              await strapi.entityService.create(
                MPAA_PROTECTION_LEVEL_STATS_NAMESPACE,
                {
                  data: {
                    area,
                    percentage,
                    total_area,
                    location: locationMap[stat.location],
                    mpaa_protection_level: MpaaProtectionLevelMap[stat.mpaa_protection_level],
                  },
                }
              );
            } else {
              // Update the existing record
              await strapi.entityService.update(
                MPAA_PROTECTION_LEVEL_STATS_NAMESPACE,
                statsMap[statKey],
                {
                  data: {
                    area,
                    percentage,
                    total_area,
                  },
                }
              );
            }
          }
        })
      return ctx.send({
        message: 'MPAA Protection Level Stats updated successfully.',
        errors: errors.length > 0 ? errors : null,
        updatedCount: data.length - errors.length,
        });
      } catch (error) {
        strapi.log.error('Error in mpaa protection level stats bulkUpdate:', error);
        return ctx.internalServerError('An error occurred while processing the request.', error.message);
      }
    }
  }));
