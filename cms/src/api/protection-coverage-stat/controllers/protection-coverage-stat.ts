/**
 * protection-coverage-stat controller
 */

import { factories } from '@strapi/strapi'

import {
    ApiEnvironmentEnvironment,
    ApiLocationLocation,
    ApiProtectionCoverageStatProtectionCoverageStat
} from '@/types/generated/contentTypes';

export default factories.createCoreController('api::protection-coverage-stat.protection-coverage-stat', ({ strapi }) => ({
    async find(ctx) {
        try {
            const { query } = ctx;
            // find the most recently updated record and return its updatedAt date
            const updatedAtQuery = {
                ...query,
                fields: ['updatedAt'],
                sort: { updatedAt: 'desc' },
                limit: 1
            };
            const updatedAt = await strapi.entityService.findMany('api::protection-coverage-stat.protection-coverage-stat', updatedAtQuery).then((data) => {
                return data[0]?.updatedAt ?? null;
            });

            const dataQuery = {
                ...query,
                pagination: { pageSize: 1000000, page: 1 } // Max allowed by the API config. Will paginate after sorting
            }
            delete dataQuery.sort; // We will sort the data after we get it
            ctx.query = dataQuery;
            // run the original find function without pagination or sorting
            const { data, meta } = await super.find(ctx);
            // Update sort so null values are at the end
            if (query?.sort) {
                const sortParams = query.sort.split(/[,:]/);
                let sortIndex = 0;
                while (sortIndex < sortParams.length) {
                    data.sort((a, b) => {
                        const first = getValueByPath(a, sortParams[sortIndex]);
                        const second = getValueByPath(b, sortParams[sortIndex]);

                        if (first === second) {
                            return 0;
                        }
                        // nulls sort after anything else
                        if (first === null || first === undefined) {
                            return 1;
                        }
                        if (second === null || second === undefined) {
                            return -1;
                        }

                        if (sortParams[sortIndex + 1] === 'asc') {
                            console.log(first, second);
                            return first < second ? -1 : 1;
                        }

                        return first < second ? 1 : -1;
                    })

                    sortIndex += 2;
                }
            }
            const [start, end] = getPaginationBounds(query.pagination, data.length);
            const paginatedData = data.slice(start, end);
            return { data: paginatedData, meta: { ...meta, updatedAt } };
        } catch (error) {
            return ctx.badRequest('Something went wrong', error);
        }
    }
}));

interface Pagination {
    start?: number;
    limit?: number;
    page?: number;
    pageSize?: number;
}

function getPaginationBounds(pagination: Pagination, dataLength: number): [number, number] {
    const { start = null, limit = 25, page = 1, pageSize = 25 } = pagination;
    if (limit === -1) {
        return [start ?? 0, dataLength];
    }
    if (start !== null && limit) {
        return [start, start + limit];
    }
    return [(page - 1) * pageSize, page * pageSize];
}

interface ProtectionCoverageStatResponse
    extends ApiProtectionCoverageStatProtectionCoverageStat {
    id: number;
    data?: ApiLocationLocation | ApiEnvironmentEnvironment
}

function getValueByPath(
    data: ProtectionCoverageStatResponse,
    path: string
): keyof ApiProtectionCoverageStatProtectionCoverageStat {
    return path.split('.').reduce((acc, key) => {
        if (!acc) {
            return null;
        }
        if (acc[key]) {
            return acc[key];
        }
        if (acc?.attributes) {
            return acc.attributes[key];
        }
        if (acc?.data) {
            return acc.data?.attributes[key];
        }

    }, data);
}