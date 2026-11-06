/** Today's date in the browser's own time zone, as YYYY-MM-DD (what the API expects for dates). */
export const todayLocal = () => new Date().toLocaleDateString("en-CA");

/** A timestamp from the API shown as YYYY-MM-DD in the browser time zone. */
export const dateOnly = (iso: string) => new Date(iso).toLocaleDateString("en-CA");
