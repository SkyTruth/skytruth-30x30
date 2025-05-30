/**
 * habitat-stat controller
 */

import { factories } from '@strapi/strapi'

export default factories.createCoreController('api::habitat-stat.habitat-stat', ({ strapi }) => ({
    async find(ctx) {
        // find the most recently updated record and return its updatedAt date
        const newQuery = {
            ...ctx.query,
            fields: ['updatedAt'],
            sort: { updatedAt: 'desc' },
            limit: 1
        };
        const updatedAt = await strapi.entityService.findMany('api::habitat-stat.habitat-stat', newQuery).then((data) => {
            return data[0]?.updatedAt ?? null;
        });
        // run the original find function
        const { data, meta } = await super.find(ctx);
        // add the updatedAt date to the meta object
        return { data, meta: { ...meta, updatedAt } }
    },
    async bulkUpsert(ctx) {
        try {
            const { data } = ctx?.request?.body;
            if (!Array.isArray(data)) {
                return ctx.badRequest('Data must be an array');
            }
            const year = parseInt(ctx.params.year, 10);
            if (isNaN(year)) {
                return ctx.badRequest('Year must be a valid number');
            }
            const errors = [];
            let locationMap: IDMap | null = null;
            let habitatMap: IDMap | null = null;
            let environmentMap: IDMap | null = null;

            const habitatStatMap: IDMap = await strapi
                .service('api::habitat-stat.habitat-stat')
                .getHabitatStatMap(year);

            await strapi.db.transaction(async () => {
                for (const stat of data) {
                    const { protected_area, total_area } = stat;
                    const statKey = `${stat.location}-${stat.environment}-${stat.habitat}`;

                    // No existing record, create a new one
                    if (!habitatStatMap[statKey]) {
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
                        if (!habitatMap) {
                            habitatMap = await strapi
                                .service('api::habitat.habitat')
                                .getHabitatMap();
                        }
                        if (!habitatMap[stat.habitat]) {
                            errors.push({
                                msg: `Failed to find habitat for stat: ${statKey}`,
                                err: `Habitat ${stat.habitat} not found`
                            });
                            continue;
                        }
                        if (!environmentMap) {
                            environmentMap = await strapi
                                .service('api::environment.environment')
                                .getEnvironmentMap();
                        }
                        if (!environmentMap[stat.environment]) {
                            errors.push({
                                msg: `Failed to find environment for stat: ${statKey}`,
                                err: `Environment ${stat.environment} not found`
                            });
                            continue;
                        }
                        await strapi.entityService.create(
                            'api::habitat-stat.habitat-stat',
                            {
                                data: {
                                    year,
                                    total_area,
                                    protected_area,
                                    location: locationMap[stat.location],
                                    habitat: habitatMap[stat.habitat],
                                    environment: environmentMap[stat.environment]
                                }
                            }
                        );
                    } else {
                        // Existing record, update it
                        await strapi.entityService.update(
                            'api::habitat-stat.habitat-stat',
                            habitatStatMap[statKey],
                            {
                                data: { total_area, protected_area }
                            }
                        );
                    }
                }
            });
            return ctx.send({
                message: 'Bulk upsert completed successfully',
                errors: errors.length > 0 ? errors : null,
            });
        } catch (error) {
            strapi.log.error('Error in habitat-stat bulkUpsert:', {error: error?.message });
            return ctx.internalServerError('An internal server error occurred during bulk upsert');
        }
    }
}));
