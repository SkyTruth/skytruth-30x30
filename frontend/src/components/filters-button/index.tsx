import { useEffect, useMemo, useRef, useState } from 'react';

import { useForm } from 'react-hook-form';

import { Filter } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { FCWithMessages } from '@/types';

const ICON_CLASSNAMES = 'h-4 w-4 fill-black';

type FiltersButtonProps = {
  field: string;
  options: {
    name: string;
    value: string;
  }[];
  values: string[];
  headerButtons?: boolean;
  showNoFiltersError?: boolean;
  onChange: (field: string, values: string[]) => void;
};

type FormValues = {
  filters: string[];
};

const FiltersButton: FCWithMessages<FiltersButtonProps> = ({
  field,
  options,
  values,
  headerButtons = true,
  showNoFiltersError = false,
  onChange,
}) => {
  const t = useTranslations('components.filters-button');

  const allFilterValues = useMemo(() => options.map(({ value }) => value), [options]);

  const [isFiltersOpen, setIsFiltersOpen] = useState<boolean>(false);

  const triggerRef = useRef<HTMLButtonElement>(null);
  const [collisionBoundary, setCollisionBoundary] = useState<Element | null>(null);

  const handleOpenChange = (open: boolean) => {
    if (open) {
      setCollisionBoundary(triggerRef.current?.closest('table')?.parentElement ?? null);
    }
    setIsFiltersOpen(open);
  };

  const { watch, setValue } = useForm<FormValues>({
    mode: 'onChange',
    defaultValues: {
      filters: values,
    },
  });

  const filters = watch('filters');

  useEffect(() => {
    setValue('filters', values);
  }, [setValue, values]);

  const handleSelectAll = () => {
    setValue('filters', allFilterValues);
    onChange(field, allFilterValues);
  };

  const handleClearAll = () => {
    setValue('filters', []);
    onChange(field, []);
  };

  const handleOnCheckedChange = (type, checked) => {
    if (checked) {
      const filtersValues = [...filters, type];
      setValue('filters', filtersValues);
      onChange(field, filtersValues);
    } else {
      const filtersValues = filters.filter((entry) => entry !== type);
      setValue('filters', filtersValues);
      onChange(field, filtersValues);
    }
  };

  const noFiltersSelected = filters.length === 0;

  return (
    <div>
      <Popover open={isFiltersOpen} onOpenChange={handleOpenChange}>
        <PopoverTrigger asChild>
          <Button ref={triggerRef} className="-ml-4" size="icon" variant="ghost">
            <span className="sr-only">{t('filter')}</span>
            <Filter className={ICON_CLASSNAMES} aria-hidden />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          collisionBoundary={collisionBoundary}
          className="flex flex-col gap-6 font-mono text-xs"
        >
          {headerButtons && (
            <div className="space-between flex gap-6">
              <Button
                className="p-0 font-bold normal-case underline hover:bg-transparent"
                variant="ghost"
                size="sm"
                onClick={handleSelectAll}
              >
                {t('select-all')}
              </Button>
              <Button
                className="p-0 font-bold normal-case text-slate-400 hover:bg-transparent hover:text-slate-400"
                variant="ghost"
                size="sm"
                onClick={handleClearAll}
              >
                {t('clear-all')}
              </Button>
            </div>
          )}
          <div className="mb-1 flex flex-col gap-5 py-2">
            <form className="flex flex-col gap-5">
              {options.map(({ name, value }) => {
                return (
                  <div key={value} className="flex items-center">
                    <Checkbox
                      name={value}
                      value={value}
                      checked={filters.includes(value)}
                      onCheckedChange={(v) => handleOnCheckedChange(value, v)}
                    />
                    <label
                      className="flex-grow cursor-pointer pl-2 pt-px text-xs leading-none text-black"
                      htmlFor={value}
                    >
                      {name}
                    </label>
                  </div>
                );
              })}
            </form>
          </div>
          {noFiltersSelected && showNoFiltersError && (
            <div className="text-orange">{t('error-no-filters')}</div>
          )}
        </PopoverContent>
      </Popover>
    </div>
  );
};

FiltersButton.messages = ['components.filters-button'];

export default FiltersButton;
