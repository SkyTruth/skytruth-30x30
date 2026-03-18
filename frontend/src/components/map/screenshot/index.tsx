import { useEffect, useState } from 'react';

import { useAtom } from 'jotai';
import { Camera, Download } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { screenshotOpenAtom } from '@/containers/map/store';
import { buildScreenshotDataUrl, downloadScreenshot } from '@/lib/utils/capture-screenshot';
import { FCWithMessages } from '@/types';

const BUTTON_CLASSES = 'group bg-white';
const ICON_CLASSES = 'text-black group-hover:text-white';

const Screenshot: FCWithMessages = () => {
  const t = useTranslations('components.map');

  const [open, setOpen] = useAtom(screenshotOpenAtom);
  const [includeLegend, setIncludeLegend] = useState(true);
  const [previewDataUrl, setPreviewDataUrl] = useState<string | null>(null);
  const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    setIsGeneratingPreview(true);
    setPreviewDataUrl(null);

    buildScreenshotDataUrl({ includeLegend })
      .then((dataUrl) => {
        if (!cancelled) setPreviewDataUrl(dataUrl);
      })
      .catch(() => {
        // Preview failed — leave null so user can still attempt download
      })
      .finally(() => {
        if (!cancelled) setIsGeneratingPreview(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, includeLegend]);

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const dataUrl = await buildScreenshotDataUrl({ includeLegend });
      downloadScreenshot(dataUrl);
      setOpen(false);
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <>
      {!open && (
        <div className="absolute right-0 top-20 z-10 mt-[0.6rem] border border-r-0 border-black">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  className={BUTTON_CLASSES}
                  onClick={() => setOpen(true)}
                >
                  <Camera className={ICON_CLASSES} aria-hidden size={18} />
                  <span className="sr-only">{t('screenshot')}</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="left">{t('screenshot-tooltip')}</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent size='large'>
          <DialogHeader>
            <DialogTitle>{t('screenshot-dialog-title')}</DialogTitle>
          </DialogHeader>

          {/* Options */}
          <div className="flex flex-col gap-3">
            <label className="flex cursor-pointer items-center gap-2 font-mono text-xs">
              <Checkbox
                name="include-legend"
                checked={includeLegend}
                onCheckedChange={(checked) => setIncludeLegend(checked === true)}
              />
              {t('screenshot-include-legend')}
            </label>
          </div>

          {/* Preview */}
          <div className="flex min-h-[200px] items-center justify-center overflow-hidden border border-black">
            {isGeneratingPreview && (
              <div className="h-full w-full" />
            )}
            {!isGeneratingPreview && previewDataUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={previewDataUrl}
                alt={t('screenshot-dialog-title')}
                className="max-h-[80vh] max-w-full object-contain"
              />
            )}
            {!isGeneratingPreview && !previewDataUrl && (
              <span className="font-mono text-xs text-gray-400">
                {t('screenshot-preview-loading')}
              </span>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              onClick={handleDownload}
              disabled={isDownloading || isGeneratingPreview}
              className="flex items-center gap-2"
            >
              <Download className="h-4 w-4" aria-hidden />
              {isDownloading ? t('screenshot-downloading') : t('screenshot-download')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

Screenshot.messages = ['components.map'];

export default Screenshot;
