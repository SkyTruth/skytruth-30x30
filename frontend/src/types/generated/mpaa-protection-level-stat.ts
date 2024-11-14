/**
 * Generated by orval v6.18.1 🍺
 * Do not edit manually.
 * DOCUMENTATION
 * OpenAPI spec version: 1.0.0
 */
import { useQuery } from '@tanstack/react-query';
import type {
  UseQueryOptions,
  QueryFunction,
  UseQueryResult,
  QueryKey,
} from '@tanstack/react-query';
import type {
  MpaaProtectionLevelStatListResponse,
  Error,
  GetMpaaProtectionLevelStatsParams,
  MpaaProtectionLevelStatResponse,
  GetMpaaProtectionLevelStatsIdParams,
} from './strapi.schemas';
import { API } from '../../services/api/index';
import type { ErrorType } from '../../services/api/index';

// eslint-disable-next-line
type SecondParameter<T extends (...args: any) => any> = T extends (
  config: any,
  args: infer P
) => any
  ? P
  : never;

export const getMpaaProtectionLevelStats = (
  params?: GetMpaaProtectionLevelStatsParams,
  options?: SecondParameter<typeof API>,
  signal?: AbortSignal
) => {
  return API<MpaaProtectionLevelStatListResponse>(
    { url: `/mpaa-protection-level-stats`, method: 'get', params, signal },
    options
  );
};

export const getGetMpaaProtectionLevelStatsQueryKey = (
  params?: GetMpaaProtectionLevelStatsParams
) => {
  return [`/mpaa-protection-level-stats`, ...(params ? [params] : [])] as const;
};

export const getGetMpaaProtectionLevelStatsQueryOptions = <
  TData = Awaited<ReturnType<typeof getMpaaProtectionLevelStats>>,
  TError = ErrorType<Error>,
>(
  params?: GetMpaaProtectionLevelStatsParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getMpaaProtectionLevelStats>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
) => {
  const { query: queryOptions, request: requestOptions } = options ?? {};

  const queryKey = queryOptions?.queryKey ?? getGetMpaaProtectionLevelStatsQueryKey(params);

  const queryFn: QueryFunction<Awaited<ReturnType<typeof getMpaaProtectionLevelStats>>> = ({
    signal,
  }) => getMpaaProtectionLevelStats(params, requestOptions, signal);

  return { queryKey, queryFn, ...queryOptions } as UseQueryOptions<
    Awaited<ReturnType<typeof getMpaaProtectionLevelStats>>,
    TError,
    TData
  > & { queryKey: QueryKey };
};

export type GetMpaaProtectionLevelStatsQueryResult = NonNullable<
  Awaited<ReturnType<typeof getMpaaProtectionLevelStats>>
>;
export type GetMpaaProtectionLevelStatsQueryError = ErrorType<Error>;

export const useGetMpaaProtectionLevelStats = <
  TData = Awaited<ReturnType<typeof getMpaaProtectionLevelStats>>,
  TError = ErrorType<Error>,
>(
  params?: GetMpaaProtectionLevelStatsParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getMpaaProtectionLevelStats>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
): UseQueryResult<TData, TError> & { queryKey: QueryKey } => {
  const queryOptions = getGetMpaaProtectionLevelStatsQueryOptions(params, options);

  const query = useQuery(queryOptions) as UseQueryResult<TData, TError> & { queryKey: QueryKey };

  query.queryKey = queryOptions.queryKey;

  return query;
};

export const getMpaaProtectionLevelStatsId = (
  id: number,
  params?: GetMpaaProtectionLevelStatsIdParams,
  options?: SecondParameter<typeof API>,
  signal?: AbortSignal
) => {
  return API<MpaaProtectionLevelStatResponse>(
    { url: `/mpaa-protection-level-stats/${id}`, method: 'get', params, signal },
    options
  );
};

export const getGetMpaaProtectionLevelStatsIdQueryKey = (
  id: number,
  params?: GetMpaaProtectionLevelStatsIdParams
) => {
  return [`/mpaa-protection-level-stats/${id}`, ...(params ? [params] : [])] as const;
};

export const getGetMpaaProtectionLevelStatsIdQueryOptions = <
  TData = Awaited<ReturnType<typeof getMpaaProtectionLevelStatsId>>,
  TError = ErrorType<Error>,
>(
  id: number,
  params?: GetMpaaProtectionLevelStatsIdParams,
  options?: {
    query?: UseQueryOptions<
      Awaited<ReturnType<typeof getMpaaProtectionLevelStatsId>>,
      TError,
      TData
    >;
    request?: SecondParameter<typeof API>;
  }
) => {
  const { query: queryOptions, request: requestOptions } = options ?? {};

  const queryKey = queryOptions?.queryKey ?? getGetMpaaProtectionLevelStatsIdQueryKey(id, params);

  const queryFn: QueryFunction<Awaited<ReturnType<typeof getMpaaProtectionLevelStatsId>>> = ({
    signal,
  }) => getMpaaProtectionLevelStatsId(id, params, requestOptions, signal);

  return { queryKey, queryFn, enabled: !!id, ...queryOptions } as UseQueryOptions<
    Awaited<ReturnType<typeof getMpaaProtectionLevelStatsId>>,
    TError,
    TData
  > & { queryKey: QueryKey };
};

export type GetMpaaProtectionLevelStatsIdQueryResult = NonNullable<
  Awaited<ReturnType<typeof getMpaaProtectionLevelStatsId>>
>;
export type GetMpaaProtectionLevelStatsIdQueryError = ErrorType<Error>;

export const useGetMpaaProtectionLevelStatsId = <
  TData = Awaited<ReturnType<typeof getMpaaProtectionLevelStatsId>>,
  TError = ErrorType<Error>,
>(
  id: number,
  params?: GetMpaaProtectionLevelStatsIdParams,
  options?: {
    query?: UseQueryOptions<
      Awaited<ReturnType<typeof getMpaaProtectionLevelStatsId>>,
      TError,
      TData
    >;
    request?: SecondParameter<typeof API>;
  }
): UseQueryResult<TData, TError> & { queryKey: QueryKey } => {
  const queryOptions = getGetMpaaProtectionLevelStatsIdQueryOptions(id, params, options);

  const query = useQuery(queryOptions) as UseQueryResult<TData, TError> & { queryKey: QueryKey };

  query.queryKey = queryOptions.queryKey;

  return query;
};
