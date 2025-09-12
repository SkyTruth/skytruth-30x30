import { FC } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import { formatKM } from '@/lib/utils/formats';

import { POPUP_BUTTON_CONTENT_BY_SOURCE } from '../constants';

import type { FormattedStat } from './hooks';

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
      <button
        type="button"
        className="mt-3 block w-full border border-black px-4 py-2.5 text-center font-mono text-xs"
        onClick={() => handleLocationSelected(formattedStat.iso)}
      >
        {t(POPUP_BUTTON_CONTENT_BY_SOURCE[source?.['id']])}
      </button>
    </>
  );
};

export default StatCard;
