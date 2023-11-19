import { ReactNode } from 'react';

import Image from 'next/image';

import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/classnames';

const IMAGES = {
  stats1: '/images/static-pages/bg-images/stats-1.png',
  stats2: '/images/static-pages/bg-images/stats-2.png',
  stats3: '/images/static-pages/bg-images/stats-3.png',
  stats4: '/images/static-pages/bg-images/stats-4.png',
};

const statsImageVariants = cva('', {
  variants: {
    color: {
      orange: 'text-orange',
      purple: 'text-purple-500',
    },
  },
  defaultVariants: {
    color: 'orange',
  },
});

export type StatsImageProps = VariantProps<typeof statsImageVariants> & {
  value: string;
  description: string | ReactNode;
  image?: keyof typeof IMAGES;
};

const StatsImage: React.FC<StatsImageProps> = ({ value, description, color, image = 'stats3' }) => (
  <div className="mt-20 flex flex-row gap-8 pb-10">
    <div className="flex w-[32%] flex-col items-center justify-end gap-5 pt-5 text-center font-mono">
      <div className="flex max-w-[240px] flex-col">
        <span className={cn('text-6xl font-bold', statsImageVariants({ color }))}>{value}</span>
        <span className="mt-5 text-xs">{description}</span>
      </div>
    </div>
    <div className="flex w-[68%] justify-end">
      <Image
        className="h-auto w-full max-w-4xl"
        src={IMAGES[image]}
        alt="Statistics image"
        width="0"
        height="0"
        sizes="100vw"
        priority
      />
    </div>
  </div>
);

export default StatsImage;
