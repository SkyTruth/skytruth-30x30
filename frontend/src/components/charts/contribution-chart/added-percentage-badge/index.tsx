import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { formatPercentage } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';

type AddedPercentageBadgeProps = {
  className?: string;
  percentage: number;
};

/**
 * Blue "+X%" badge: how much the drawn shape adds to the protected percentage. The box
 * scales with its font size, so a text size in `className` makes it larger or smaller
 */
const AddedPercentageBadge: FCWithMessages<AddedPercentageBadgeProps> = ({
  className,
  percentage,
}) => {
  const t = useTranslations('components.chart-contribution');
  const locale = useLocale();

  return (
    <span
      className={cn(
        'inline-flex items-center bg-blue-700 px-1.5 pb-[0.27em] pt-[0.47em] text-base font-bold text-white',
        className,
        'leading-none'
      )}
    >
      <span>
        {t.rich('added-percentage', {
          percentage: formatPercentage(locale, percentage, { displayPercentageSign: false }),
          sign: (chunks) => <span className="text-[0.7em]">{chunks}</span>,
        })}
      </span>
    </span>
  );
};

AddedPercentageBadge.messages = ['components.chart-contribution'];

export default AddedPercentageBadge;
