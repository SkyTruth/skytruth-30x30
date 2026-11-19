export function formatPercentage(
  locale: string,
  value: number,
  options?: Intl.NumberFormatOptions & {
    displayPercentageSign?: boolean;
    displayZeroValue?: boolean;
  }
) {
  const {
    displayPercentageSign = true,
    displayZeroValue = true,
    ...intlNumberFormatOptions
  } = options || {};

  const v = Intl.NumberFormat(locale === 'en' ? 'en-US' : locale, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
    style: displayPercentageSign ? 'percent' : 'decimal',
    ...intlNumberFormatOptions,
  });
  // Formats a percentage from 0 to 100 (the percent style expects a fraction from 0 to 1)
  const format = (percentage: number) =>
    v.format(displayPercentageSign ? percentage / 100 : percentage);

  if (value < 0.1 && (!displayZeroValue || (displayZeroValue && value > 0))) {
    return `<${format(0.1)}`;
  }

  // Sanity check to prevent the display of percentages over 100.
  // This should never be true, but data can be wonky hence this last resort check.
  if (value > 100) {
    return format(100);
  }

  return format(value);
}

export function formatNumber(locale: string, value: number, options?: Intl.NumberFormatOptions) {
  const formatter = Intl.NumberFormat(locale === 'en' ? 'en-US' : locale, options);
  return formatter.format(value);
}

export function formatKM(locale: string, value: number, options?: Intl.NumberFormatOptions) {
  if (value < 1 && value > 0) return '<1';

  const v = Intl.NumberFormat(locale === 'en' ? 'en-US' : locale, {
    notation: 'standard',
    compactDisplay: 'short',
    unit: 'kilometer',
    unitDisplay: 'short',
    maximumFractionDigits: 0,
    ...options,
  });

  return v.format(value);
}

const FORMATS = {
  formatPercentage,
  formatNumber,
  formatKM,
} as const;

export type FormatProps = {
  locale: string;
  value: unknown;
  id?: keyof typeof FORMATS;
  options?: Intl.NumberFormatOptions;
};

export function format({ locale, id, value, options }: FormatProps) {
  const fn = id ? FORMATS[id] : undefined;

  if (typeof fn === 'function' && typeof value === 'number') {
    return fn(locale, value, options);
  }

  if (typeof value === 'number') {
    return value.toLocaleString();
  }

  if (typeof value === 'string') {
    return value;
  }
}

export default FORMATS;
