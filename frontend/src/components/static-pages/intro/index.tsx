import { ReactNode } from 'react';

import { VariantProps, cva } from 'class-variance-authority';

import Icon from '@/components/ui/icon';
import { cn } from '@/lib/classnames';
import ArrowRight from '@/styles/icons/arrow-right.svg';

const BACKGROUND_IMAGES = {
  computer: '/images/static-pages/bg-images/card-1.png',
  magnifyingGlass: '/images/static-pages/bg-images/card-2.png',
  tablet: '/images/static-pages/bg-images/card-3.png',
};

const introVariants = cva('', {
  variants: {
    color: {
      green: 'bg-green',
      purple: 'bg-purple-400',
    },
  },
  defaultVariants: {
    color: 'green',
  },
});

type IntroProps = VariantProps<typeof introVariants> & {
  title: string;
  description?: string | ReactNode;
  image?: string;
  onScrollClick: () => void;
};

const Intro: React.FC<IntroProps> = ({
  title,
  description,
  color,
  image = 'computer',
  onScrollClick,
}) => (
  <div className={cn('bg-black', introVariants({ color }))}>
    <div className="flex flex-col md:mx-auto md:max-w-7xl md:flex-row">
      <div className="mb-2 mt-6 flex flex-1 flex-col px-8">
        <div className="pr-10 text-5xl font-extrabold leading-tight md:text-6xl">{title}</div>
        <div className="flex flex-1 flex-col justify-end pb-8">
          {description && <div className="pr-[20%] text-xl">{description}</div>}
        </div>
      </div>
      <div className="w-full border-l border-r border-black md:w-[40%]">
        <div className="flex h-full flex-col">
          <span
            className="aspect-[1.8] max-h-[160px] w-full flex-shrink-0 border-b border-t border-black bg-cover bg-center bg-no-repeat mix-blend-multiply md:max-h-[70%] md:border-t-0"
            style={{
              backgroundImage: `url(${BACKGROUND_IMAGES[image]})`,
            }}
          />
          <div className="flex aspect-[1.8] h-full max-h-[140px] w-full justify-center md:max-h-[50%] md:min-h-0">
            <button
              className="my-6 flex aspect-square items-center justify-center md:w-auto"
              type="button"
              onClick={onScrollClick}
            >
              <Icon icon={ArrowRight} className="h-[80%] rotate-90 fill-black md:h-[60%]" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
);

export default Intro;
