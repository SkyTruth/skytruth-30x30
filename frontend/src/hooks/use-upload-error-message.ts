import { useCallback } from 'react';

import { useTranslations } from 'next-intl';

import { UploadErrorType } from '@/lib/utils/file-upload';

type UseUploadErrorMessageParams = {
  maxFileSize: number;
};

export class FileTooLargeError extends Error {
  constructor(message?: string) {
    super(message ?? 'File too Large');
    this.name = 'FileTooLargeError';
  }
}

export const useUploadErrorMessage = ({ maxFileSize }: UseUploadErrorMessageParams) => {
  const t = useTranslations('services.uploads');

  return useCallback(
    (error: unknown) => {
      if (error instanceof FileTooLargeError) {
        return t('file-too-large-error', { size: `${maxFileSize / 1000000}Mb` });
      }

      switch (error) {
        case UploadErrorType.InvalidXMLSyntax:
          return t('xml-syntax-error');
        case UploadErrorType.SHPMissingFile:
          return t('shp-missing-files-error');
        case UploadErrorType.UnsupportedFile:
          return t('unsupported-file-error');
        default:
          return t('generic-upload-error');
      }
    },
    [maxFileSize, t]
  );
};
