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
  DatasetListResponse,
  Error,
  GetDatasetsParams,
  DatasetResponse,
  DatasetRequest,
  GetDatasetsIdParams,
  DatasetLocalizationResponse,
  DatasetLocalizationRequest,
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

export const getDatasets = (
  params?: GetDatasetsParams,
  options?: SecondParameter<typeof API>,
  signal?: AbortSignal
) => {
  return API<DatasetListResponse>({ url: `/datasets`, method: 'get', params, signal }, options);
};

export const getGetDatasetsQueryKey = (params?: GetDatasetsParams) => {
  return [`/datasets`, ...(params ? [params] : [])] as const;
};

export const getGetDatasetsQueryOptions = <
  TData = Awaited<ReturnType<typeof getDatasets>>,
  TError = ErrorType<Error>,
>(
  params?: GetDatasetsParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDatasets>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
) => {
  const { query: queryOptions, request: requestOptions } = options ?? {};

  const queryKey = queryOptions?.queryKey ?? getGetDatasetsQueryKey(params);

  const queryFn: QueryFunction<Awaited<ReturnType<typeof getDatasets>>> = ({ signal }) =>
    getDatasets(params, requestOptions, signal);

  return { queryKey, queryFn, ...queryOptions } as UseQueryOptions<
    Awaited<ReturnType<typeof getDatasets>>,
    TError,
    TData
  > & { queryKey: QueryKey };
};

export type GetDatasetsQueryResult = NonNullable<Awaited<ReturnType<typeof getDatasets>>>;
export type GetDatasetsQueryError = ErrorType<Error>;

export const useGetDatasets = <
  TData = Awaited<ReturnType<typeof getDatasets>>,
  TError = ErrorType<Error>,
>(
  params?: GetDatasetsParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDatasets>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
): UseQueryResult<TData, TError> & { queryKey: QueryKey } => {
  const queryOptions = getGetDatasetsQueryOptions(params, options);

  const query = useQuery(queryOptions) as UseQueryResult<TData, TError> & { queryKey: QueryKey };

  query.queryKey = queryOptions.queryKey;

  return query;
};

export const postDatasets = (
  datasetRequest: BodyType<DatasetRequest>,
  options?: SecondParameter<typeof API>
) => {
  return API<DatasetResponse>(
    {
      url: `/datasets`,
      method: 'post',
      headers: { 'Content-Type': 'application/json' },
      data: datasetRequest,
    },
    options
  );
};

export const getPostDatasetsMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown,
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDatasets>>,
    TError,
    { data: BodyType<DatasetRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof postDatasets>>,
  TError,
  { data: BodyType<DatasetRequest> },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof postDatasets>>,
    { data: BodyType<DatasetRequest> }
  > = (props) => {
    const { data } = props ?? {};

    return postDatasets(data, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type PostDatasetsMutationResult = NonNullable<Awaited<ReturnType<typeof postDatasets>>>;
export type PostDatasetsMutationBody = BodyType<DatasetRequest>;
export type PostDatasetsMutationError = ErrorType<Error>;

export const usePostDatasets = <TError = ErrorType<Error>, TContext = unknown>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDatasets>>,
    TError,
    { data: BodyType<DatasetRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getPostDatasetsMutationOptions(options);

  return useMutation(mutationOptions);
};
export const getDatasetsId = (
  id: number,
  params?: GetDatasetsIdParams,
  options?: SecondParameter<typeof API>,
  signal?: AbortSignal
) => {
  return API<DatasetResponse>({ url: `/datasets/${id}`, method: 'get', params, signal }, options);
};

export const getGetDatasetsIdQueryKey = (id: number, params?: GetDatasetsIdParams) => {
  return [`/datasets/${id}`, ...(params ? [params] : [])] as const;
};

export const getGetDatasetsIdQueryOptions = <
  TData = Awaited<ReturnType<typeof getDatasetsId>>,
  TError = ErrorType<Error>,
>(
  id: number,
  params?: GetDatasetsIdParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDatasetsId>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
) => {
  const { query: queryOptions, request: requestOptions } = options ?? {};

  const queryKey = queryOptions?.queryKey ?? getGetDatasetsIdQueryKey(id, params);

  const queryFn: QueryFunction<Awaited<ReturnType<typeof getDatasetsId>>> = ({ signal }) =>
    getDatasetsId(id, params, requestOptions, signal);

  return { queryKey, queryFn, enabled: !!id, ...queryOptions } as UseQueryOptions<
    Awaited<ReturnType<typeof getDatasetsId>>,
    TError,
    TData
  > & { queryKey: QueryKey };
};

export type GetDatasetsIdQueryResult = NonNullable<Awaited<ReturnType<typeof getDatasetsId>>>;
export type GetDatasetsIdQueryError = ErrorType<Error>;

export const useGetDatasetsId = <
  TData = Awaited<ReturnType<typeof getDatasetsId>>,
  TError = ErrorType<Error>,
>(
  id: number,
  params?: GetDatasetsIdParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDatasetsId>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
): UseQueryResult<TData, TError> & { queryKey: QueryKey } => {
  const queryOptions = getGetDatasetsIdQueryOptions(id, params, options);

  const query = useQuery(queryOptions) as UseQueryResult<TData, TError> & { queryKey: QueryKey };

  query.queryKey = queryOptions.queryKey;

  return query;
};

export const putDatasetsId = (
  id: number,
  datasetRequest: BodyType<DatasetRequest>,
  options?: SecondParameter<typeof API>
) => {
  return API<DatasetResponse>(
    {
      url: `/datasets/${id}`,
      method: 'put',
      headers: { 'Content-Type': 'application/json' },
      data: datasetRequest,
    },
    options
  );
};

export const getPutDatasetsIdMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown,
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof putDatasetsId>>,
    TError,
    { id: number; data: BodyType<DatasetRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof putDatasetsId>>,
  TError,
  { id: number; data: BodyType<DatasetRequest> },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof putDatasetsId>>,
    { id: number; data: BodyType<DatasetRequest> }
  > = (props) => {
    const { id, data } = props ?? {};

    return putDatasetsId(id, data, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type PutDatasetsIdMutationResult = NonNullable<Awaited<ReturnType<typeof putDatasetsId>>>;
export type PutDatasetsIdMutationBody = BodyType<DatasetRequest>;
export type PutDatasetsIdMutationError = ErrorType<Error>;

export const usePutDatasetsId = <TError = ErrorType<Error>, TContext = unknown>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof putDatasetsId>>,
    TError,
    { id: number; data: BodyType<DatasetRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getPutDatasetsIdMutationOptions(options);

  return useMutation(mutationOptions);
};
export const deleteDatasetsId = (id: number, options?: SecondParameter<typeof API>) => {
  return API<number>({ url: `/datasets/${id}`, method: 'delete' }, options);
};

export const getDeleteDatasetsIdMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown,
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof deleteDatasetsId>>,
    TError,
    { id: number },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof deleteDatasetsId>>,
  TError,
  { id: number },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof deleteDatasetsId>>,
    { id: number }
  > = (props) => {
    const { id } = props ?? {};

    return deleteDatasetsId(id, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type DeleteDatasetsIdMutationResult = NonNullable<
  Awaited<ReturnType<typeof deleteDatasetsId>>
>;

export type DeleteDatasetsIdMutationError = ErrorType<Error>;

export const useDeleteDatasetsId = <TError = ErrorType<Error>, TContext = unknown>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof deleteDatasetsId>>,
    TError,
    { id: number },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getDeleteDatasetsIdMutationOptions(options);

  return useMutation(mutationOptions);
};
export const postDatasetsIdLocalizations = (
  id: number,
  datasetLocalizationRequest: BodyType<DatasetLocalizationRequest>,
  options?: SecondParameter<typeof API>
) => {
  return API<DatasetLocalizationResponse>(
    {
      url: `/datasets/${id}/localizations`,
      method: 'post',
      headers: { 'Content-Type': 'application/json' },
      data: datasetLocalizationRequest,
    },
    options
  );
};

export const getPostDatasetsIdLocalizationsMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown,
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDatasetsIdLocalizations>>,
    TError,
    { id: number; data: BodyType<DatasetLocalizationRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof postDatasetsIdLocalizations>>,
  TError,
  { id: number; data: BodyType<DatasetLocalizationRequest> },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof postDatasetsIdLocalizations>>,
    { id: number; data: BodyType<DatasetLocalizationRequest> }
  > = (props) => {
    const { id, data } = props ?? {};

    return postDatasetsIdLocalizations(id, data, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type PostDatasetsIdLocalizationsMutationResult = NonNullable<
  Awaited<ReturnType<typeof postDatasetsIdLocalizations>>
>;
export type PostDatasetsIdLocalizationsMutationBody = BodyType<DatasetLocalizationRequest>;
export type PostDatasetsIdLocalizationsMutationError = ErrorType<Error>;

export const usePostDatasetsIdLocalizations = <
  TError = ErrorType<Error>,
  TContext = unknown,
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDatasetsIdLocalizations>>,
    TError,
    { id: number; data: BodyType<DatasetLocalizationRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getPostDatasetsIdLocalizationsMutationOptions(options);

  return useMutation(mutationOptions);
};
