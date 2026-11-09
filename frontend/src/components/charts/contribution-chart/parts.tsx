import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { formatKM, formatPercentage } from '@/lib/utils/formats';
import { Contribution } from '@/lib/utils/modelling-contributions';

export const MAX_PERCENTAGE = 100;

// Width of a bar segment, capped at the full bar
export const toWidth = (percentage: number) => `${Math.min(percentage, MAX_PERCENTAGE)}%`;

/**
 * Blue "+X%" badge: how much the drawn shape adds to the protected percentage. The box
 * scales with its font size, so a text size in `className` makes it larger or smaller
 */
export const AddedPercentageBadge = ({
  className,
  percentage,
}: {
  className?: string;
  percentage: number;
}) => {
  const t = useTranslations('components.chart-contribution');
  const locale = useLocale();

  return (
    <span
      className={cn(
        'inline-flex items-center bg-blue-700 px-1.5 pb-[0.27em] pt-[0.47em] text-base font-bold leading-none text-white',
        className
      )}
    >
      <span>
        {t('added-percentage', {
          percentage: formatPercentage(locale, percentage, { displayPercentageSign: false }),
        })}
        <span className="text-[0.7em]">%</span>
      </span>
    </span>
  );
};

type ContributionBarProps = {
  className?: string;
  contribution: Contribution;
  // Color of the existing area; gray when unset
  existingColor?: string;
  // Target line position in %; no line when unset
  target?: number;
};

/** Bar of the existing area then the added area (blue), with a dashed line for the rest */
export const ContributionBar = ({
  className,
  contribution: { existingPercentage, addedPercentage },
  existingColor,
  target,
}: ContributionBarProps) => (
  <div className={cn('relative h-3.5', className)}>
    <span className="absolute top-1/2 h-px w-full border-b border-dashed border-black" />
    <span
      className={cn('absolute bottom-0 left-0 top-0', { 'bg-existing-area': !existingColor })}
      style={{ width: toWidth(existingPercentage), backgroundColor: existingColor }}
    />
    <span
      className="absolute bottom-0 top-0 bg-blue-700"
      style={{ left: toWidth(existingPercentage), width: toWidth(addedPercentage) }}
    />
    {target != null && (
      <span
        className="absolute -bottom-1 -top-1 w-0.5 -translate-x-1/2 bg-orange-700"
        style={{ left: toWidth(target) }}
      />
    )}
  </div>
);

/** "N km² (+M km²) of T km² protected", with the added part in blue */
export const ProtectedAreaText = ({
  className,
  contribution: { existing, added, total },
}: {
  className?: string;
  contribution: Contribution;
}) => {
  const t = useTranslations('components.chart-contribution');
  const locale = useLocale();

  return (
    <div className={cn('text-xs', className)}>
      {t.rich('protected-area', {
        protectedArea: formatKM(locale, existing + added),
        addedArea: formatKM(locale, added),
        totalArea: formatKM(locale, total),
        added: (chunks) => <span className="text-blue-700">{chunks}</span>,
      })}
    </div>
  );
};
