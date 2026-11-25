import { PropsWithChildren } from 'react';

import { cn } from '@/lib/classnames';

const LegendItem = ({ className, children }: PropsWithChildren<{ className: string }>) => (
  <li className="flex items-center gap-2">
    <span aria-hidden className={cn('h-2.5 w-2.5 border border-black', className)} />
    <span className="pt-[0.2em] leading-none">{children}</span>
  </li>
);

export default LegendItem;
