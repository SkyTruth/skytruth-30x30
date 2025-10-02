import { FC, useEffect, useState } from 'react';

import Link from 'next/link';

import { useTranslations } from 'next-intl';

import { PAGES } from '@/constants/pages';
import {
  useMapSearchParams,
  useSyncCustomRegion,
} from '@/containers/map/content/map/sync-settings';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

import { useNeedsTruncate } from './hooks';

type CountriesListProps = {
  className?: HTMLDivElement['className'];
  bgColorClassName: string;
  countries: {
    code: string;
    name: string;
  }[];
  isCustomRegion?: boolean;
};

type ClearCustomRegionButtonProps = {
  className?: string;
};
const CountriesList: FCWithMessages<CountriesListProps> = ({
  className,
  countries,
  bgColorClassName,
  isCustomRegion = false,
}) => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const [isListOpen, setListOpen] = useState(false);
  const searchParams = useMapSearchParams();
  const customRegionsSync = useSyncCustomRegion();
  const setCustomRegionLocations = customRegionsSync[1];

  const { containerRef, needsTruncate } = useNeedsTruncate<HTMLDivElement>(12, 2, [countries]);

  useEffect(() => {
    setListOpen(false);
  }, [countries]);

  const handleClearCustomRegion = (): void => {
    setCustomRegionLocations(new Set());
  };

  const ClearCustomRegionButton: FC<ClearCustomRegionButtonProps> = ({ className = '' }) => {
    return (
      <span
        className={cn('cursor-pointer font-semibold underline', className)}
        onClick={handleClearCustomRegion}
      >
        {t('clear-custom-region')}
      </span>
    );
  };

  if (!countries?.length) return null;

  return (
    <div className={cn('font-mono text-xs leading-5', className)}>
      <div
        ref={containerRef}
        className={cn({
          'relative overflow-hidden': true,
          'max-h-[38px]': !isListOpen,
          'max-h-full': isListOpen,
        })}
      >
        {countries.map(({ code, name }, idx) => (
          <span key={code}>
            <Link
              className="underline"
              href={`${PAGES.progressTracker}/${code}?${searchParams.toString()}`}
            >
              {name}
            </Link>
            {idx < countries?.length - 1 && <>, </>}
          </span>
        ))}
        {!isListOpen && needsTruncate && (
          <span className="absolute -bottom-0.5 right-0 flex pl-2">
            <span className="block w-10 bg-gradient-to-l from-orange to-transparent" />
            <span className={cn('px-1', bgColorClassName)}>....</span>
          </span>
        )}
      </div>
      <div className="mt-2">
        <span
          className="cursor-pointer font-semibold underline pr-3"
          onClick={() => setListOpen(!isListOpen)}
        >
          {isListOpen && t('hide-some-countries')}
          {!isListOpen && needsTruncate && t('view-all-countries')}
        </span>
      {isCustomRegion && <ClearCustomRegionButton />}
      </div>
    </div>
  );
};

CountriesList.messages = ['containers.map-sidebar-main-panel'];

export default CountriesList;
