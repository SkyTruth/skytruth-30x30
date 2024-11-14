/**
 * Generated by orval v6.18.1 🍺
 * Do not edit manually.
 * DOCUMENTATION
 * OpenAPI spec version: 1.0.0
 */
import { useQuery, useMutation } from '@tanstack/react-query';
import type {
  UseQueryOptions,
  UseMutationOptions,
  QueryFunction,
  MutationFunction,
  UseQueryResult,
  QueryKey,
} from '@tanstack/react-query';
import type {
  DataSourceListResponse,
  Error,
  GetDataSourcesParams,
  DataSourceResponse,
  GetDataSourcesIdParams,
  DataSourceLocalizationResponse,
  DataSourceLocalizationRequest,
} from './strapi.schemas';
import { API } from '../../services/api/index';
import type { ErrorType, BodyType } from '../../services/api/index';

// eslint-disable-next-line
type SecondParameter<T extends (...args: any) => any> = T extends (
  config: any,
  args: infer P
) => any
  ? P
  : never;

export const getDataSources = (
  params?: GetDataSourcesParams,
  options?: SecondParameter<typeof API>,
  signal?: AbortSignal
) => {
  return API<DataSourceListResponse>(
    { url: `/data-sources`, method: 'get', params, signal },
    options
  );
};

export const getGetDataSourcesQueryKey = (params?: GetDataSourcesParams) => {
  return [`/data-sources`, ...(params ? [params] : [])] as const;
};

export const getGetDataSourcesQueryOptions = <
  TData = Awaited<ReturnType<typeof getDataSources>>,
  TError = ErrorType<Error>,
>(
  params?: GetDataSourcesParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDataSources>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
) => {
  const { query: queryOptions, request: requestOptions } = options ?? {};

  const queryKey = queryOptions?.queryKey ?? getGetDataSourcesQueryKey(params);

  const queryFn: QueryFunction<Awaited<ReturnType<typeof getDataSources>>> = ({ signal }) =>
    getDataSources(params, requestOptions, signal);

  return { queryKey, queryFn, ...queryOptions } as UseQueryOptions<
    Awaited<ReturnType<typeof getDataSources>>,
    TError,
    TData
  > & { queryKey: QueryKey };
};

export type GetDataSourcesQueryResult = NonNullable<Awaited<ReturnType<typeof getDataSources>>>;
export type GetDataSourcesQueryError = ErrorType<Error>;

export const useGetDataSources = <
  TData = Awaited<ReturnType<typeof getDataSources>>,
  TError = ErrorType<Error>,
>(
  params?: GetDataSourcesParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDataSources>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
): UseQueryResult<TData, TError> & { queryKey: QueryKey } => {
  const queryOptions = getGetDataSourcesQueryOptions(params, options);

  const query = useQuery(queryOptions) as UseQueryResult<TData, TError> & { queryKey: QueryKey };

  query.queryKey = queryOptions.queryKey;

  return query;
};

export const getDataSourcesId = (
  id: number,
  params?: GetDataSourcesIdParams,
  options?: SecondParameter<typeof API>,
  signal?: AbortSignal
) => {
  return API<DataSourceResponse>(
    { url: `/data-sources/${id}`, method: 'get', params, signal },
    options
  );
};

export const getGetDataSourcesIdQueryKey = (id: number, params?: GetDataSourcesIdParams) => {
  return [`/data-sources/${id}`, ...(params ? [params] : [])] as const;
};

export const getGetDataSourcesIdQueryOptions = <
  TData = Awaited<ReturnType<typeof getDataSourcesId>>,
  TError = ErrorType<Error>,
>(
  id: number,
  params?: GetDataSourcesIdParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDataSourcesId>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
) => {
  const { query: queryOptions, request: requestOptions } = options ?? {};

  const queryKey = queryOptions?.queryKey ?? getGetDataSourcesIdQueryKey(id, params);

  const queryFn: QueryFunction<Awaited<ReturnType<typeof getDataSourcesId>>> = ({ signal }) =>
    getDataSourcesId(id, params, requestOptions, signal);

  return { queryKey, queryFn, enabled: !!id, ...queryOptions } as UseQueryOptions<
    Awaited<ReturnType<typeof getDataSourcesId>>,
    TError,
    TData
  > & { queryKey: QueryKey };
};

export type GetDataSourcesIdQueryResult = NonNullable<Awaited<ReturnType<typeof getDataSourcesId>>>;
export type GetDataSourcesIdQueryError = ErrorType<Error>;

export const useGetDataSourcesId = <
  TData = Awaited<ReturnType<typeof getDataSourcesId>>,
  TError = ErrorType<Error>,
>(
  id: number,
  params?: GetDataSourcesIdParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDataSourcesId>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
): UseQueryResult<TData, TError> & { queryKey: QueryKey } => {
  const queryOptions = getGetDataSourcesIdQueryOptions(id, params, options);

  const query = useQuery(queryOptions) as UseQueryResult<TData, TError> & { queryKey: QueryKey };

  query.queryKey = queryOptions.queryKey;

  return query;
};

export const postDataSourcesIdLocalizations = (
  id: number,
  dataSourceLocalizationRequest: BodyType<DataSourceLocalizationRequest>,
  options?: SecondParameter<typeof API>
) => {
  return API<DataSourceLocalizationResponse>(
    {
      url: `/data-sources/${id}/localizations`,
      method: 'post',
      headers: { 'Content-Type': 'application/json' },
      data: dataSourceLocalizationRequest,
    },
    options
  );
};

export const getPostDataSourcesIdLocalizationsMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown,
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDataSourcesIdLocalizations>>,
    TError,
    { id: number; data: BodyType<DataSourceLocalizationRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof postDataSourcesIdLocalizations>>,
  TError,
  { id: number; data: BodyType<DataSourceLocalizationRequest> },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof postDataSourcesIdLocalizations>>,
    { id: number; data: BodyType<DataSourceLocalizationRequest> }
  > = (props) => {
    const { id, data } = props ?? {};

    return postDataSourcesIdLocalizations(id, data, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type PostDataSourcesIdLocalizationsMutationResult = NonNullable<
  Awaited<ReturnType<typeof postDataSourcesIdLocalizations>>
>;
export type PostDataSourcesIdLocalizationsMutationBody = BodyType<DataSourceLocalizationRequest>;
export type PostDataSourcesIdLocalizationsMutationError = ErrorType<Error>;

export const usePostDataSourcesIdLocalizations = <
  TError = ErrorType<Error>,
  TContext = unknown,
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDataSourcesIdLocalizations>>,
    TError,
    { id: number; data: BodyType<DataSourceLocalizationRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getPostDataSourcesIdLocalizationsMutationOptions(options);

  return useMutation(mutationOptions);
};
