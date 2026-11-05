/** Today's date in the browser's own time zone, as YYYY-MM-DD (what the API expects for dates). */
export const todayLocal = () => new Date().toLocaleDateString("en-CA");
