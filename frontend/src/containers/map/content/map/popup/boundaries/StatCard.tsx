import { FC, useCallback } from 'react';

import { useRouter } from 'next/router';

import { useLocale, useTranslations } from 'next-intl';

import { useAtom } from 'jotai';

import { formatKM } from '@/lib/utils/formats';

import { POPUP_BUTTON_CONTENT_BY_SOURCE } from '../constants';

import type { FormattedStat } from './hooks';
import { useSetCustomRegionLocations } from '@/hooks/useCustomRegionsLocations';
import { CUSTOM_REGION_CODE } from '@/containers/map/constants';
import { PlusCircle } from 'lucide-react';
import { customRegionLocationsAtom } from '@/containers/map/store';

interface StatCardProps {
  environment: string;
  formattedStat: FormattedStat;
  handleLocationSelected: (iso: string) => void;
  source: string;
}

const StatCard: FC<StatCardProps> = ({
  environment,
  formattedStat,
  handleLocationSelected,
  source,
}) => {
  const t = useTranslations('containers.map');
  const locale = useLocale();
  const {
    query: { locationCode = 'GLOB'}
  } = useRouter();

  const [customRegionLocations] = useAtom(customRegionLocationsAtom)

  const code = Array.isArray(locationCode) ? locationCode[0] : locationCode;
  const isCustomRegionActive = CUSTOM_REGION_CODE === code;

  const handleAddToCustomRegion = useCallback((code: string) => {
    // useSetCustomRegionLocations([...customRegionLocations, code])
  },[])

  return (
    <>
      <div className="flex flex-col gap-2">
        <div className="max-w-[95%] font-mono">
          {environment === 'marine'
            ? t('marine-conservation-coverage')
            : t('terrestrial-conservation-coverage')}
        </div>
        <div className="space-x-1 font-mono tracking-tighter text-black">
          {formattedStat.percentage !== '-' &&
            t.rich('percentage-bold', {
              percentage: formattedStat.percentage,
              b1: (chunks) => <span className="text-[32px] font-bold leading-none">{chunks}</span>,
              b2: (chunks) => <span className="text-lg">{chunks}</span>,
            })}
          {formattedStat.percentage === '-' && (
            <span className="text-xl font-bold leading-none">{formattedStat.percentage}</span>
          )}
        </div>
        <div className="space-x-1 font-mono font-medium text-black">
          {t.rich('protected-area', {
            br: () => <br />,
            protectedArea: formattedStat.protectedArea,
            totalArea: formatKM(locale, Number(formattedStat.totalArea)),
          })}
        </div>
      </div>
      {isCustomRegionActive ?
        <button 
          className="inline-flex w-full font-mono text-xs text-left py-2 justify-left"
          onClick={() => handleAddToCustomRegion(formattedStat.iso)}
          >
            <PlusCircle className='mr-2 h-4 w-4 pb-px' />Add to Custom Region
        </button>
        : null
      }
      <button
        type="button"
        className="block w-full border border-black px-4 py-2.5 text-center font-mono text-xs"
        onClick={() => handleLocationSelected(formattedStat.iso)}
      >
        {t(POPUP_BUTTON_CONTENT_BY_SOURCE[source?.['id']])}
      </button>
    </>
  );
};

export default StatCard;
