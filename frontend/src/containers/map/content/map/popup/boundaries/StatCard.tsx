import { FC, useCallback } from 'react';

import { useRouter } from 'next/router';

import { PlusCircle } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { cn } from '@/lib/classnames';
import { formatKM } from '@/lib/utils/formats';

import { useSyncCustomRegion } from '../../sync-settings';
import { POPUP_BUTTON_CONTENT_BY_SOURCE, CUSTOM_REGION_ELIGABILITY_BY_SOURCE } from '../constants';

import type { FormattedStat } from './hooks';
interface StatCardProps {
  environment: string;
  formattedStat: FormattedStat;
  handleLocationSelected: (iso: string) => void;
  source: { [key: string]: string };
}

const StatCard: FC<StatCardProps> = ({
  environment,
  formattedStat: { iso, percentage, protectedArea, totalArea },
  handleLocationSelected,
  source,
}) => {
  const t = useTranslations('containers.map');
  const locale = useLocale();
  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const [customRegionLocations, setCustomRegionLocations] = useSyncCustomRegion();

  const code = Array.isArray(locationCode) ? locationCode[0] : locationCode;
  const isCustomRegionActive =
    CUSTOM_REGION_CODE === code && CUSTOM_REGION_ELIGABILITY_BY_SOURCE.has(source.id);

  const handleAddToCustomRegion = useCallback(
    (code: string) => {
      const newLocs = new Set(customRegionLocations);
      newLocs.add(code);
      setCustomRegionLocations(newLocs);
    },
    [setCustomRegionLocations, customRegionLocations]
  );

  const handleRemoveFromCustomRegion = useCallback(
    (code: string) => {
      const newLocs = new Set(customRegionLocations);
      newLocs.delete(code);
      setCustomRegionLocations(new Set(newLocs));
    },
    [setCustomRegionLocations, customRegionLocations]
  );

  const isLocatonInCustomRegion = customRegionLocations.has(iso);

  return (
    <>
      <div className="flex flex-col gap-2">
        <div className="max-w-[95%] font-mono">
          {environment === 'marine'
            ? t('marine-conservation-coverage')
            : t('terrestrial-conservation-coverage')}
        </div>
        <div className="space-x-1 font-mono tracking-tighter text-black">
          {percentage !== '-' &&
            t.rich('percentage-bold', {
              percentage: percentage,
              b1: (chunks) => <span className="text-[32px] font-bold leading-none">{chunks}</span>,
              b2: (chunks) => <span className="text-lg">{chunks}</span>,
            })}
          {percentage === '-' && (
            <span className="text-xl font-bold leading-none">{percentage}</span>
          )}
        </div>
        <div className="space-x-1 font-mono font-medium text-black">
          {t.rich('protected-area', {
            br: () => <br />,
            protectedArea: protectedArea,
            totalArea: formatKM(locale, Number(totalArea)),
          })}
        </div>
      </div>
      {isCustomRegionActive && !iso.endsWith('*') ? (
        <button
          className="justify-left inline-flex w-full py-2 text-left font-mono text-xs"
          onClick={
            isLocatonInCustomRegion
              ? () => handleRemoveFromCustomRegion(iso)
              : () => handleAddToCustomRegion(iso)
          }
        >
          <PlusCircle
            className={cn(
              { 'rotate-45': isLocatonInCustomRegion },
              'ease-&lsqb;cubic-bezier(0.87,_0,_0.13,_1)&rsqb; mr-2 h-4 w-4 pb-px transition-transform duration-300'
            )}
          />
          {isLocatonInCustomRegion ? t('remove-from-custom-region') : t('add-to-custom-region')}
        </button>
      ) : null}
      <button
        type="button"
        className="block w-full border border-black px-4 py-2.5 text-center font-mono text-xs"
        onClick={() => handleLocationSelected(iso)}
      >
        {t(POPUP_BUTTON_CONTENT_BY_SOURCE[source?.['id']])}
      </button>
    </>
  );
};

export default StatCard;
