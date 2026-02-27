import { useEffect, useState } from 'react';

import Image from 'next/image';

import { useAtomValue } from 'jotai';
import { useTranslations } from 'next-intl';

import {
  Carousel,
  CarouselApi,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '@/components/ui/carousel';
import { drawStateAtom } from '@/containers/map/store';
import { FCWithMessages } from '@/types';

const snapFormat = new Intl.NumberFormat(undefined, {
  minimumIntegerDigits: 2,
});

const ModellingIntro: FCWithMessages = () => {
  const t = useTranslations('containers.map-sidebar-main-panel');

  const { active, status } = useAtomValue(drawStateAtom);
  const [current, setCurrent] = useState(1);
  const [api, setApi] = useState<CarouselApi>();

  useEffect(() => {
    if (!api) {
      return;
    }

    api.on('select', () => {
      setCurrent(api.selectedScrollSnap() + 1);
    });
  }, [api]);

  useEffect(() => {
    let step = null;

    if (!api) {
      return;
    }

    if (active) {
      step = 2;
      setCurrent(step);
      api.scrollTo(step - 1);
    }

    if (status === 'drawing') {
      step = 3;
      setCurrent(step);
      api.scrollTo(step - 1);
    }
  }, [active, status, api]);

  return (
    <div className="flex flex-col gap-4 px-4 py-4 md:px-8">
      <span className="text-xl font-bold">
        {t.rich('how-to-draw', {
          b: (chunks) => <span className="text-blue-600">{chunks}</span>,
        })}
      </span>

      <Carousel
        setApi={setApi}
        opts={{
          duration: 0,
        }}
        className="space-y-1"
      >
        <div className="flex items-end justify-between">
          <span className="font-mono text-lg">
            {snapFormat.format(current)}—
            <span className="text-black/20">
              {api ? snapFormat.format(api.scrollSnapList().length) : '-'}
            </span>
          </span>
          <div className="space-x-2">
            <CarouselPrevious className="static translate-y-0" />
            <CarouselNext className="static translate-y-0" />
          </div>
        </div>
        <CarouselContent>
          <CarouselItem>
            <div className="space-y-2">
              <p>
                {t.rich('step-1-description', {
                  b: (chunks) => <span className="font-bold">{chunks}</span>,
                })}
              </p>
            </div>
          </CarouselItem>
          <CarouselItem>
            <div className="space-y-2">
              <Image
                className="w-full"
                src="/images/drawing-steps/02.webp"
                alt={t('step-2-alt')}
                quality={100}
                width={375}
                height={143}
              />
              <p>
                {t.rich('step-2-description', {
                  b: (chunks) => <span className="font-bold">{chunks}</span>,
                })}
              </p>
            </div>
          </CarouselItem>
          <CarouselItem>
            <div className="space-y-2">
              <Image
                className="w-full"
                src="/images/drawing-steps/03.webp"
                alt={t('step-3-alt')}
                quality={100}
                width={375}
                height={143}
              />
              <p>
                {t.rich('step-3-description', {
                  b: (chunks) => <span className="font-bold">{chunks}</span>,
                })}
              </p>
            </div>
          </CarouselItem>
        </CarouselContent>
      </Carousel>
    </div>
  );
};

ModellingIntro.messages = [
  'containers.map-sidebar-main-panel',
  ...CarouselPrevious.messages,
  ...CarouselNext.messages,
];

export default ModellingIntro;
