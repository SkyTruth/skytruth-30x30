import { useEffect, useMemo, useState } from 'react';

import { useRouter } from 'next/router';

import { SortingState, PaginationState } from '@tanstack/react-table';
import { usePreviousImmediate } from 'rooks';

import FiltersButton from '@/components/filters-button';
import TooltipButton from '@/components/tooltip-button';
import { Skeleton } from '@/components/ui/skeleton';
import Table from '@/containers/map/content/details/table';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { FCWithMessages } from '@/types';

import SortingButton from '../../table/sorting-button';

import { useColumns, useData } from './hooks';

const GlobalRegionalTable: FCWithMessages = () => {
  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const [{ tab }] = useSyncMapContentSettings();
  const previousTab = usePreviousImmediate(tab);

  const [filters, setFilters] = useState<Record<string, string[]>>({});

  const columns = useColumns(
    tab === 'marine' || tab === 'terrestrial' ? tab : null,
    filters,
    setFilters
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
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 100,
  });

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

  // When the tab changes, we reset the filters and the sorting
  useEffect(() => {
    if (tab !== previousTab) {
      setFilters({});
      setSorting(defaultSorting);
    }
  }, [tab, previousTab, defaultSorting]);

  // When the filters or the sorting changes, the page number is reset
  useEffect(() => {
    setPagination((prevPagination) => ({ ...prevPagination, pageIndex: 0 }));
  }, [filters, sorting]);

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
        // @ts-ignore
        columns={newColumns}
        data={newData}
        sorting={sorting}
        onSortingChange={setSorting}
        pagination={pagination}
        onPaginationChange={setPagination}
        rowCount={total ?? 0}
      />
    );
  }

  return (
    <Table
      // @ts-ignore
      columns={columns}
      data={data}
      sorting={sorting}
      onSortingChange={setSorting}
      pagination={pagination}
      onPaginationChange={setPagination}
      rowCount={total ?? 0}
    />
  );
};

GlobalRegionalTable.messages = [
  'containers.map',
  ...Table.messages,
  // Dependencies of `useColumns`
  ...SortingButton.messages,
  ...TooltipButton.messages,
  ...FiltersButton.messages,
];

export default GlobalRegionalTable;
