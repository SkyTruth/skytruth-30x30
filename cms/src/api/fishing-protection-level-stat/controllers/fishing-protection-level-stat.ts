/**
 * fishing-protection-level-stat controller
 */

import { factories } from '@strapi/strapi'


export default factories
.createCoreController('api::fishing-protection-level-stat.fishing-protection-level-stat' , ({ strapi }) => ({
  async bulkUpsert(ctx) {
    try {
      const { data } = ctx?.request?.body;
      if (!Array.isArray(data)) {
        return ctx.badRequest('Data must be an array');
      }
      const errors = [];
      let locationMap: IDMap | null = null;
      let fishingProtectionLevelMap: IDMap | null = null;
      await strapi.db.transaction(async () => {
        const statsMap: IDMap = await strapi
          .service('api::fishing-protection-level-stat.fishing-protection-level-stat')
          .getFishingProtectionLevelStatsMap();

        for (const stat of data) {
          const { area, pct, total_area } = stat;
          const statKey = `${stat.location}-${stat.fishing_protection_level}`;

          // No existing record, create a new one
          if (!statsMap[statKey]) {
            if (!locationMap) {
              locationMap = await strapi
                .service('api::location.location')
                .getLocationMap();
            }
            if (!locationMap[stat.location]) {
              errors.push({
                msg: `Failed to find location for stat: ${statKey}`,
                err: `Location ${stat.location} not found`
              });
              continue;
            }
            if (!fishingProtectionLevelMap) {
              fishingProtectionLevelMap = await strapi
                .service('api::fishing-protection-level.fishing-protection-level')
                .getFishingProtectionLevelMap();
            }
            if (!fishingProtectionLevelMap[stat.fishing_protection_level]) {
              errors.push({
                msg: `Failed to find fishing protection level for stat: ${statKey}`,
                err: `Fishing Protection Level ${stat.fishing_protection_level} not found`
              });
              continue;
            }
            await strapi.entityService.create(
              'api::fishing-protection-level-stat.fishing-protection-level-stat',
              {
                data: {
                  area,
                  pct,
                  total_area,
                  location: locationMap[stat.location],
                  fishing_protection_level: fishingProtectionLevelMap[stat.fishing_protection_level],
                },
              }
            );
          } else {
            // Update existing record
            await strapi.entityService.update(
              'api::fishing-protection-level-stat.fishing-protection-level-stat',
              statsMap[statKey],
              {
                data: { area, pct, total_area },
              }
            );
          }
        }
        return ctx.send({
          message: 'Bulk upsert completed successfully',
          errors: errors.length > 0 ? errors : null,
        })
      });
    } catch (error) {
      console.error('Error in fishing stats bulkUpsert:', error);
      return ctx.internalServerError('An error occurred while processing the request');
    }
  }
})); 
    