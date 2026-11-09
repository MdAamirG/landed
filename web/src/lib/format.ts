/** Rupees for display, in the Indian grouping: 3380000 paise is "33,800". */
export function rupees(paise: number): string {
  // Display only: every calculation stays in integer paise. Whole rupees drop the ".00", as in
  // the design, but part of a rupee always shows both digits.
  const decimals = paise % 100 === 0 ? 0 : 2;
  return new Intl.NumberFormat("en-IN", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(paise / 100);
}
