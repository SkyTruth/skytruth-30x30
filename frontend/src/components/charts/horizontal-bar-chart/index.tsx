import { useMemo } from 'react';

import { useLocale, useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { cn } from '@/lib/classnames';
import { formatPercentage, formatKM } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';

const DEFAULT_MAX_PERCENTAGE = 100;
const PROTECTION_TARGET = 30;

interface Source {
  id: number;
  title: string;
  url: string;
}

interface HorizontalBarChartProps {
  className: string;
  data: {
    background: string;
    title?: string;
    totalArea: number;
    protectedArea: number;
    percentage?: number;
    info?: string;
    sources?: Source | Source[];
  };
  showLegend?: boolean;
  showTarget?: boolean;
}

const HorizontalBarChart: FCWithMessages<HorizontalBarChartProps> = ({
  className,
  data,
  showLegend = true,
  showTarget = true,
}) => {
  const t = useTranslations('components.chart-horizontal-bar');
  const locale = useLocale();

  const { title, background, totalArea, percentage, protectedArea, info, sources } = data;

  const percent = useMemo(() => {
    return percentage ?? (protectedArea / totalArea) * 100;
  }, [percentage]);

  const targetPositionPercentage = useMemo(() => {
    return (PROTECTION_TARGET * 100) / DEFAULT_MAX_PERCENTAGE;
  }, []);

  const protectedAreaPercentage = useMemo(() => {
    return formatPercentage(locale, percent, {
      displayPercentageSign: false,
    });
  }, [locale, totalArea, protectedArea]);

  const barFillPercentage = useMemo(() => {
    // Prevent overflowing if the bar fill exceeds the set max percentage
    return percent > DEFAULT_MAX_PERCENTAGE ? 100 : percent;
  }, [protectedArea, totalArea]);

  return (
    <div className={cn('font-mono', className)}>
      <div className="space-y-2">
        <div className="flex justify-between text-xs">
          {title && <h3 className="font-sans text-base font-bold">{title}</h3>}
          {info && <TooltipButton text={info} sources={sources} />}
        </div>
        <div className="text-4xl font-bold">
          {t.rich('marine-protected-percentage', {
            b: (chunks) => <span className="pb-1.5 pl-1 text-xs">{chunks}</span>,
            percentage: protectedAreaPercentage,
          })}
        </div>
      </div>
      <span className="text-xs">
        {t('marine-protected-area', {
          protectedArea: formatKM(locale, protectedArea),
          totalArea: formatKM(locale, totalArea),
        })}
      </span>
      <div className="relative mb-2 flex h-3.5">
        <span className="absolute top-1/2 h-px w-full border-b border-dashed border-black"></span>
        <span
          className="absolute bottom-0 left-0 top-0 border border-black !bg-cover"
          style={{
            background,
            width: `${barFillPercentage}%`,
          }}
        />
        {showTarget && (
          <span
            className="absolute bottom-0 top-0 w-1 border-x border-white bg-orange"
            style={{
              left: `${targetPositionPercentage}%`,
            }}
          >
            <span className="absolute left-0 top-5 whitespace-nowrap text-xs text-orange">
              {t('30%-target')}
            </span>
          </span>
        )}
      </div>
      {showLegend && (
        <div className="flex justify-between text-xs">
          <span>{t('percentage', { percentage: 0 })}</span>
          <span>{t('percentage', { percentage: DEFAULT_MAX_PERCENTAGE })}</span>
        </div>
      )}
    </div>
  );
};

HorizontalBarChart.messages = ['components.chart-horizontal-bar'];

export default HorizontalBarChart;
