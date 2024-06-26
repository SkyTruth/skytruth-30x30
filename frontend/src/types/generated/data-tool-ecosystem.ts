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
  DataToolEcosystemListResponse,
  Error,
  GetDataToolEcosystemsParams,
  DataToolEcosystemResponse,
  DataToolEcosystemRequest,
  GetDataToolEcosystemsIdParams,
  DataToolEcosystemLocalizationResponse,
  DataToolEcosystemLocalizationRequest,
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

export const getDataToolEcosystems = (
  params?: GetDataToolEcosystemsParams,
  options?: SecondParameter<typeof API>,
  signal?: AbortSignal
) => {
  return API<DataToolEcosystemListResponse>(
    { url: `/data-tool-ecosystems`, method: 'get', params, signal },
    options
  );
};

export const getGetDataToolEcosystemsQueryKey = (params?: GetDataToolEcosystemsParams) => {
  return [`/data-tool-ecosystems`, ...(params ? [params] : [])] as const;
};

export const getGetDataToolEcosystemsQueryOptions = <
  TData = Awaited<ReturnType<typeof getDataToolEcosystems>>,
  TError = ErrorType<Error>
>(
  params?: GetDataToolEcosystemsParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDataToolEcosystems>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
) => {
  const { query: queryOptions, request: requestOptions } = options ?? {};

  const queryKey = queryOptions?.queryKey ?? getGetDataToolEcosystemsQueryKey(params);

  const queryFn: QueryFunction<Awaited<ReturnType<typeof getDataToolEcosystems>>> = ({ signal }) =>
    getDataToolEcosystems(params, requestOptions, signal);

  return { queryKey, queryFn, ...queryOptions } as UseQueryOptions<
    Awaited<ReturnType<typeof getDataToolEcosystems>>,
    TError,
    TData
  > & { queryKey: QueryKey };
};

export type GetDataToolEcosystemsQueryResult = NonNullable<
  Awaited<ReturnType<typeof getDataToolEcosystems>>
>;
export type GetDataToolEcosystemsQueryError = ErrorType<Error>;

export const useGetDataToolEcosystems = <
  TData = Awaited<ReturnType<typeof getDataToolEcosystems>>,
  TError = ErrorType<Error>
>(
  params?: GetDataToolEcosystemsParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDataToolEcosystems>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
): UseQueryResult<TData, TError> & { queryKey: QueryKey } => {
  const queryOptions = getGetDataToolEcosystemsQueryOptions(params, options);

  const query = useQuery(queryOptions) as UseQueryResult<TData, TError> & { queryKey: QueryKey };

  query.queryKey = queryOptions.queryKey;

  return query;
};

export const postDataToolEcosystems = (
  dataToolEcosystemRequest: BodyType<DataToolEcosystemRequest>,
  options?: SecondParameter<typeof API>
) => {
  return API<DataToolEcosystemResponse>(
    {
      url: `/data-tool-ecosystems`,
      method: 'post',
      headers: { 'Content-Type': 'application/json' },
      data: dataToolEcosystemRequest,
    },
    options
  );
};

export const getPostDataToolEcosystemsMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDataToolEcosystems>>,
    TError,
    { data: BodyType<DataToolEcosystemRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof postDataToolEcosystems>>,
  TError,
  { data: BodyType<DataToolEcosystemRequest> },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof postDataToolEcosystems>>,
    { data: BodyType<DataToolEcosystemRequest> }
  > = (props) => {
    const { data } = props ?? {};

    return postDataToolEcosystems(data, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type PostDataToolEcosystemsMutationResult = NonNullable<
  Awaited<ReturnType<typeof postDataToolEcosystems>>
>;
export type PostDataToolEcosystemsMutationBody = BodyType<DataToolEcosystemRequest>;
export type PostDataToolEcosystemsMutationError = ErrorType<Error>;

export const usePostDataToolEcosystems = <TError = ErrorType<Error>, TContext = unknown>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDataToolEcosystems>>,
    TError,
    { data: BodyType<DataToolEcosystemRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getPostDataToolEcosystemsMutationOptions(options);

  return useMutation(mutationOptions);
};
export const getDataToolEcosystemsId = (
  id: number,
  params?: GetDataToolEcosystemsIdParams,
  options?: SecondParameter<typeof API>,
  signal?: AbortSignal
) => {
  return API<DataToolEcosystemResponse>(
    { url: `/data-tool-ecosystems/${id}`, method: 'get', params, signal },
    options
  );
};

export const getGetDataToolEcosystemsIdQueryKey = (
  id: number,
  params?: GetDataToolEcosystemsIdParams
) => {
  return [`/data-tool-ecosystems/${id}`, ...(params ? [params] : [])] as const;
};

export const getGetDataToolEcosystemsIdQueryOptions = <
  TData = Awaited<ReturnType<typeof getDataToolEcosystemsId>>,
  TError = ErrorType<Error>
>(
  id: number,
  params?: GetDataToolEcosystemsIdParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDataToolEcosystemsId>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
) => {
  const { query: queryOptions, request: requestOptions } = options ?? {};

  const queryKey = queryOptions?.queryKey ?? getGetDataToolEcosystemsIdQueryKey(id, params);

  const queryFn: QueryFunction<Awaited<ReturnType<typeof getDataToolEcosystemsId>>> = ({
    signal,
  }) => getDataToolEcosystemsId(id, params, requestOptions, signal);

  return { queryKey, queryFn, enabled: !!id, ...queryOptions } as UseQueryOptions<
    Awaited<ReturnType<typeof getDataToolEcosystemsId>>,
    TError,
    TData
  > & { queryKey: QueryKey };
};

export type GetDataToolEcosystemsIdQueryResult = NonNullable<
  Awaited<ReturnType<typeof getDataToolEcosystemsId>>
>;
export type GetDataToolEcosystemsIdQueryError = ErrorType<Error>;

export const useGetDataToolEcosystemsId = <
  TData = Awaited<ReturnType<typeof getDataToolEcosystemsId>>,
  TError = ErrorType<Error>
>(
  id: number,
  params?: GetDataToolEcosystemsIdParams,
  options?: {
    query?: UseQueryOptions<Awaited<ReturnType<typeof getDataToolEcosystemsId>>, TError, TData>;
    request?: SecondParameter<typeof API>;
  }
): UseQueryResult<TData, TError> & { queryKey: QueryKey } => {
  const queryOptions = getGetDataToolEcosystemsIdQueryOptions(id, params, options);

  const query = useQuery(queryOptions) as UseQueryResult<TData, TError> & { queryKey: QueryKey };

  query.queryKey = queryOptions.queryKey;

  return query;
};

export const putDataToolEcosystemsId = (
  id: number,
  dataToolEcosystemRequest: BodyType<DataToolEcosystemRequest>,
  options?: SecondParameter<typeof API>
) => {
  return API<DataToolEcosystemResponse>(
    {
      url: `/data-tool-ecosystems/${id}`,
      method: 'put',
      headers: { 'Content-Type': 'application/json' },
      data: dataToolEcosystemRequest,
    },
    options
  );
};

export const getPutDataToolEcosystemsIdMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof putDataToolEcosystemsId>>,
    TError,
    { id: number; data: BodyType<DataToolEcosystemRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof putDataToolEcosystemsId>>,
  TError,
  { id: number; data: BodyType<DataToolEcosystemRequest> },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof putDataToolEcosystemsId>>,
    { id: number; data: BodyType<DataToolEcosystemRequest> }
  > = (props) => {
    const { id, data } = props ?? {};

    return putDataToolEcosystemsId(id, data, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type PutDataToolEcosystemsIdMutationResult = NonNullable<
  Awaited<ReturnType<typeof putDataToolEcosystemsId>>
>;
export type PutDataToolEcosystemsIdMutationBody = BodyType<DataToolEcosystemRequest>;
export type PutDataToolEcosystemsIdMutationError = ErrorType<Error>;

export const usePutDataToolEcosystemsId = <
  TError = ErrorType<Error>,
  TContext = unknown
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof putDataToolEcosystemsId>>,
    TError,
    { id: number; data: BodyType<DataToolEcosystemRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getPutDataToolEcosystemsIdMutationOptions(options);

  return useMutation(mutationOptions);
};
export const deleteDataToolEcosystemsId = (id: number, options?: SecondParameter<typeof API>) => {
  return API<number>({ url: `/data-tool-ecosystems/${id}`, method: 'delete' }, options);
};

export const getDeleteDataToolEcosystemsIdMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof deleteDataToolEcosystemsId>>,
    TError,
    { id: number },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof deleteDataToolEcosystemsId>>,
  TError,
  { id: number },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof deleteDataToolEcosystemsId>>,
    { id: number }
  > = (props) => {
    const { id } = props ?? {};

    return deleteDataToolEcosystemsId(id, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type DeleteDataToolEcosystemsIdMutationResult = NonNullable<
  Awaited<ReturnType<typeof deleteDataToolEcosystemsId>>
>;

export type DeleteDataToolEcosystemsIdMutationError = ErrorType<Error>;

export const useDeleteDataToolEcosystemsId = <
  TError = ErrorType<Error>,
  TContext = unknown
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof deleteDataToolEcosystemsId>>,
    TError,
    { id: number },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getDeleteDataToolEcosystemsIdMutationOptions(options);

  return useMutation(mutationOptions);
};
export const postDataToolEcosystemsIdLocalizations = (
  id: number,
  dataToolEcosystemLocalizationRequest: BodyType<DataToolEcosystemLocalizationRequest>,
  options?: SecondParameter<typeof API>
) => {
  return API<DataToolEcosystemLocalizationResponse>(
    {
      url: `/data-tool-ecosystems/${id}/localizations`,
      method: 'post',
      headers: { 'Content-Type': 'application/json' },
      data: dataToolEcosystemLocalizationRequest,
    },
    options
  );
};

export const getPostDataToolEcosystemsIdLocalizationsMutationOptions = <
  TError = ErrorType<Error>,
  TContext = unknown
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDataToolEcosystemsIdLocalizations>>,
    TError,
    { id: number; data: BodyType<DataToolEcosystemLocalizationRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}): UseMutationOptions<
  Awaited<ReturnType<typeof postDataToolEcosystemsIdLocalizations>>,
  TError,
  { id: number; data: BodyType<DataToolEcosystemLocalizationRequest> },
  TContext
> => {
  const { mutation: mutationOptions, request: requestOptions } = options ?? {};

  const mutationFn: MutationFunction<
    Awaited<ReturnType<typeof postDataToolEcosystemsIdLocalizations>>,
    { id: number; data: BodyType<DataToolEcosystemLocalizationRequest> }
  > = (props) => {
    const { id, data } = props ?? {};

    return postDataToolEcosystemsIdLocalizations(id, data, requestOptions);
  };

  return { mutationFn, ...mutationOptions };
};

export type PostDataToolEcosystemsIdLocalizationsMutationResult = NonNullable<
  Awaited<ReturnType<typeof postDataToolEcosystemsIdLocalizations>>
>;
export type PostDataToolEcosystemsIdLocalizationsMutationBody =
  BodyType<DataToolEcosystemLocalizationRequest>;
export type PostDataToolEcosystemsIdLocalizationsMutationError = ErrorType<Error>;

export const usePostDataToolEcosystemsIdLocalizations = <
  TError = ErrorType<Error>,
  TContext = unknown
>(options?: {
  mutation?: UseMutationOptions<
    Awaited<ReturnType<typeof postDataToolEcosystemsIdLocalizations>>,
    TError,
    { id: number; data: BodyType<DataToolEcosystemLocalizationRequest> },
    TContext
  >;
  request?: SecondParameter<typeof API>;
}) => {
  const mutationOptions = getPostDataToolEcosystemsIdLocalizationsMutationOptions(options);

  return useMutation(mutationOptions);
};
