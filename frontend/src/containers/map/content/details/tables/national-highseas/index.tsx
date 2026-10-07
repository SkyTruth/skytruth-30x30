import { useCallback, useEffect, useMemo, useState } from 'react';

import { useRouter } from 'next/router';

import { OnChangeFn, PaginationState, SortingState } from '@tanstack/react-table';
import { usePreviousImmediate } from 'rooks';

import FiltersButton from '@/components/filters-button';
import TooltipButton from '@/components/tooltip-button';
import { Skeleton } from '@/components/ui/skeleton';
import Table from '@/containers/map/content/details/table';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { FCWithMessages } from '@/types';

import SortingButton from '../../table/sorting-button';

import { useData, useColumns } from './hooks';

const NationalHighseasTable: FCWithMessages = () => {
  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const [{ tab }] = useSyncMapContentSettings();
  const previousTab = usePreviousImmediate(tab);

  const [filters, setFilters] = useState<Record<string, string[]>>({});
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 100,
  });

  const resetPageIndex = useCallback(() => {
    setPagination((prevPagination) => ({ ...prevPagination, pageIndex: 0 }));
  }, []);

  const onFiltersChange = useCallback(
    (newFilters: Record<string, string[]>) => {
      setFilters(newFilters);
      resetPageIndex();
    },
    [resetPageIndex]
  );

  const columns = useColumns(
    tab === 'marine' || tab === 'terrestrial' ? tab : null,
    filters,
    onFiltersChange
  );

  const defaultSorting = useMemo(
    () => [
      {
        id: columns[0].accessorKey,
        desc: false,
      },
    ],
    [columns]
  );

  const [sorting, setSorting] = useState<SortingState>(defaultSorting);

  const onSortingChange: OnChangeFn<SortingState> = useCallback(
    (updater) => {
      setSorting(updater);
      resetPageIndex();
    },
    [resetPageIndex]
  );

  const {
    data: [data, { total }],
    isLoading,
    isFetching,
  } = useData(
    locationCode as string,
    tab === 'marine' || tab === 'terrestrial' ? tab : null,
    sorting,
    filters,
    pagination
  );

  // When the tab changes, reset the filters, sorting, and page number
  useEffect(() => {
    if (tab !== previousTab) {
      setFilters({});
      setSorting(defaultSorting);
      resetPageIndex();
    }
  }, [tab, previousTab, defaultSorting, resetPageIndex]);

  // While the data is loading, we're showing a table with skeletons
  if (isLoading || isFetching) {
    const newColumns = columns.map((column) => ({
      ...column,
      cell: () => (
        <div className="text-4xl font-bold">
          <Skeleton className="my-3 h-4 w-full" />
        </div>
      ),
    }));

    const newData = data.length > 0 ? data : [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];

    return (
      <Table
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore
        columns={newColumns}
        data={newData}
        sorting={sorting}
        onSortingChange={onSortingChange}
        pagination={pagination}
        onPaginationChange={setPagination}
        rowCount={total ?? 0}
      />
    );
  }

  return (
    <Table
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      columns={columns}
      data={data}
      sorting={sorting}
      onSortingChange={onSortingChange}
      pagination={pagination}
      onPaginationChange={setPagination}
      rowCount={total ?? 0}
    />
  );
};

NationalHighseasTable.messages = [
  'containers.map',
  ...Table.messages,
  // Dependencies of `useColumns`
  ...SortingButton.messages,
  ...TooltipButton.messages,
  ...FiltersButton.messages,
];

export default NationalHighseasTable;
