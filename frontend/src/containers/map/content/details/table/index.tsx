import { useCallback, useMemo, useRef } from 'react';

import {
  AccessorKeyColumnDef,
  flexRender,
  getCoreRowModel,
  getExpandedRowModel,
  PaginationState,
  SortingState,
  useReactTable,
} from '@tanstack/react-table';
import { useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

import Pagination from './pagination';
import ScrollingIndicators from './scrolling-indicators';

type MapTableProps<TData> = FCWithMessages<{
  columns: AccessorKeyColumnDef<TData>[];
  data: TData[];
  columnSeparators?: string[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  pagination: PaginationState;
  onPaginationChange: (pagination: PaginationState) => void;
  rowCount: number;
}>;

const MapTable: MapTableProps<unknown> = <TData,>({
  columns,
  data,
  columnSeparators = null,
  sorting,
  onSortingChange,
  pagination,
  onPaginationChange,
  rowCount,
}) => {
  const t = useTranslations('containers.map');

  const tableRef = useRef<HTMLTableElement>();
  const firstColumnRef = useRef<HTMLTableCellElement>(null);

  const table = useReactTable({
    data,
    columns,
    getSubRows: (row) => row['subRows'] as TData[] | undefined,
    getCoreRowModel: getCoreRowModel(),
    getExpandedRowModel: getExpandedRowModel(),
    manualFiltering: true,
    manualSorting: true,
    manualPagination: true,
    state: {
      sorting,
      pagination,
    },
    onSortingChange,
    onPaginationChange,
    rowCount,
    defaultColumn: {
      size: 200,
    },
  });

  // NOTE: do not memoize so that the table is re-rendered if the data changes
  const hasData = table.getRowModel().rows?.length > 0;

  const firstColumn = useMemo(() => columns[0], [columns]);
  const lastColumn = useMemo(() => columns[columns.length - 1], [columns]);

  const shouldAddColumnSeparator = useCallback(
    (columnId) => {
      return columnSeparators ? columnSeparators?.includes(columnId) : false;
    },
    [columnSeparators]
  );

  return (
    <div className="flex h-full flex-col">
      <div className="relative flex-grow overflow-hidden pt-5">
        <ScrollingIndicators className="h-full w-full overflow-scroll">
          <table
            ref={tableRef}
            className="relative border-separate border-spacing-0 whitespace-nowrap font-mono text-xs"
          >
            <thead className="sticky top-0 z-10 bg-white text-left">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id} className="shadow-[0_2px_0_-1px_rgb(0,0,0)]">
                  {headerGroup.headers.map((header) => {
                    const { id, column } = header;
                    const isFirstColumn = id === firstColumn.accessorKey;
                    const isLastColumn = id === lastColumn.accessorKey;
                    const isMapColumn = column.id === 'map';

                    return (
                      <th
                        key={id}
                        ref={isFirstColumn ? firstColumnRef : null}
                        className={cn({
                          'border-r border-black': shouldAddColumnSeparator(id),
                          'h-10 overflow-hidden': true,
                          'px-6': !isMapColumn,
                          'sticky left-0 z-10 border-r border-r-black bg-white pl-0 pr-5':
                            isFirstColumn,
                          'pr-0': isLastColumn,
                        })}
                        style={{
                          minWidth: column.getSize() ? `${column.getSize()}px` : undefined,
                          width: column.getSize() ? `${column.getSize()}px` : undefined,
                          maxWidth: column.getSize() ? `${column.getSize() + 15}px` : undefined,
                        }}
                      >
                        {flexRender(column.columnDef.header, header.getContext())}
                      </th>
                    );
                  })}
                </tr>
              ))}
            </thead>
            <tbody>
              {hasData &&
                table.getRowModel().rows.map((row, idx) => {
                  const isFirstRow = idx === 0;
                  const isLastRow = idx + 1 === table.getRowModel().rows.length;
                  const isLastSubRow =
                    row.depth === 1 &&
                    row.getParentRow().subRows.findIndex(({ id }) => id === row.id) ===
                      row.getParentRow().subRows.length - 1;

                  return (
                    <tr
                      key={row.id}
                      className={cn({
                        relative: true,
                        'after:absolute after:-bottom-px after:left-0 after:z-10 after:block after:h-px after:w-full after:bg-black':
                          isLastSubRow,
                      })}
                    >
                      {row.getVisibleCells().map((cell) => {
                        const { column } = cell;
                        const isFirstColumn = column.id === firstColumn.accessorKey;
                        const isLastColumn = column.id === lastColumn.accessorKey;
                        const isMapColumn = column.id === 'map';

                        return (
                          <td
                            key={cell.id}
                            className={cn({
                              'overflow-hidden whitespace-normal py-5 pl-6': true,
                              'px-6': !isMapColumn,
                              '-mb-px -mt-px': isMapColumn,
                              'sticky left-0 border-r border-r-black bg-white pl-0 pr-5':
                                isFirstColumn,
                              'pr-0': isLastColumn,
                              'border-r border-black': shouldAddColumnSeparator(column.id),
                              'border-t border-t-black': !isFirstRow,
                              '[border-top-style:dashed]': !isFirstRow && !row.getIsExpanded(),
                              'border-b border-b-black': isLastRow,
                            })}
                            style={{
                              minWidth: column.getSize() ? `${column.getSize()}px` : undefined,
                              width: column.getSize() ? `${column.getSize()}px` : undefined,
                              maxWidth: column.getSize() ? `${column.getSize()}px` : undefined,
                            }}
                          >
                            {flexRender(column.columnDef.cell, cell.getContext())}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}

              {!hasData && (
                <tr>
                  <td colSpan={columns.length} className="h-24 text-center">
                    {t('no-results')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </ScrollingIndicators>
      </div>
      <Pagination table={table} pagination={pagination} rowCount={rowCount} />
    </div>
  );
};

MapTable.messages = ['containers.map'];

export default MapTable;
