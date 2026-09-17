import { useLocale, useTranslations } from 'next-intl';

import TooltipButton from '@/components/tooltip-button';
import { cn } from '@/lib/classnames';
import { formatPercentage, formatKM } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';

const DEFAULT_MAX_PERCENTAGE = 100;

type StackedHorizontalBarChartProps = {
  className: string;
  title?: string;
  info?: string;
  customArea: number;
  totalProtectedArea: number;
  totalArea: number;
  highlightedPercentage: number;
  data: {
    background: string;
    total: number;
    totalPercentage: number;
  }[];
  overlays?: {
    background: string;
    outlineColor: string;
    startPercentage: number;
    totalPercentage: number;
  }[];
  showLegend?: boolean;
  showTarget?: boolean;
};

const StackedHorizontalBarChart: FCWithMessages<StackedHorizontalBarChartProps> = ({
  className,
  data,
  title,
  info,
  customArea,
  totalProtectedArea,
  totalArea,
  highlightedPercentage,
  overlays = [],
  showLegend = true,
  showTarget = true,
}) => {
  const t = useTranslations('components.chart-stacked-horizontal-bar');
  const locale = useLocale();

  return (
    <div className={cn('font-mono', className)}>
      <div className="flex items-end justify-end text-3xl font-bold">
        {formatPercentage(locale, highlightedPercentage, { displayPercentageSign: false })}
        <span className="pb-1.5 pl-1 text-xs">%</span>
      </div>
      <div className="flex items-start justify-between text-xs">
        <span className="flex items-center">
          {title && title}
          {info && <TooltipButton text={info} />}
        </span>
        <div>
          <div className="text-right">
            {t('marine-protected-area', {
              protectedArea: formatKM(locale, totalProtectedArea),
              totalArea: formatKM(locale, totalArea),
            })}
          </div>
          <div className="text-right">
            {t('new-added-area', {
              area: formatKM(locale, customArea),
            })}
          </div>
        </div>
      </div>
      <div className="relative my-2 flex h-3.5">
        <span className="absolute top-1/2 h-px w-full border-b border-dashed border-black"></span>
        {data.map((item, index) => (
          <span
            key={index}
            className="absolute bottom-0 left-0 top-0 !bg-cover"
            style={{
              background: item.background,
              width: `${item.totalPercentage}%`,
              ...(index > 0 && { left: `${data[index - 1].totalPercentage}%` }),
            }}
          />
        ))}
        {overlays.map((overlay, index) => (
          <span
            key={index}
            className="absolute bottom-0 top-0"
            style={{
              background: overlay.background,
              boxShadow: `inset 0 0 0 1px ${overlay.outlineColor}`,
              left: `${overlay.startPercentage}%`,
              width: `${overlay.totalPercentage}%`,
            }}
          />
        ))}
        {showTarget && (
          <span className="absolute bottom-0 left-[30%] top-0 w-1 border-x border-white bg-orange">
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

StackedHorizontalBarChart.messages = [
  'components.chart-stacked-horizontal-bar',
  ...TooltipButton.messages,
];

export default StackedHorizontalBarChart;
