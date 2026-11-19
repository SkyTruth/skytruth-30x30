import type { UseQueryResult } from '@tanstack/react-query';

// Request state of a stat that loads separately from coverage
export type StatStatus = 'loading' | 'error' | 'success';

export const toStatus = (
  ...queries: Pick<UseQueryResult, 'isError' | 'isInitialLoading'>[]
): StatStatus => {
  if (queries.some(({ isError }) => isError)) return 'error';
  if (queries.some(({ isInitialLoading }) => isInitialLoading)) return 'loading';
  return 'success';
};
