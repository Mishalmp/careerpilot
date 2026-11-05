"use client";

import { todayLocal } from "@/lib/dates";

import { useState } from "react";

import {
  button,
  card,
  input,
  muted,
  primaryButton,
  select,
} from "@/components/ui";

import {
  type Offer,
  useCompareOffers,
  useDeleteRate,
  useRates,
  useSetRate,
} from "./hooks";

const CURRENCIES = [
  "INR",
  "USD",
  "EUR",
  "GBP",
  "AED",
  "CAD",
  "AUD",
  "SGD",
] as const;
type Currency = (typeof CURRENCIES)[number];

type Row = {
  name: string;
  currency: Currency;
  fixed: string;
  variable: string;
  payout: string;
  bonus: string;
  equity: string;
  notice: string;
  joining: string;
};

const blank = (n: number): Row => ({
  name: `Offer ${n}`,
  currency: "INR",
  fixed: "",
  variable: "",
  payout: "100",
  bonus: "",
  equity: "",
  notice: "",
  joining: "",
});

const money = (value: string | null | undefined) =>
  value === null || value === undefined
    ? "n/a"
    : Number(value).toLocaleString("en-IN");

function toOffer(row: Row): Offer {
  return {
    name: row.name.trim() || "Offer",
    currency: row.currency,
    fixed_annual: row.fixed || "0",
    variable_target_annual: row.variable || "0",
    variable_payout_pct: row.payout || "100",
    joining_bonus: row.bonus || "0",
    equity_annual_value: row.equity || "0",
    notice_days: Number(row.notice || 0),
    joining_date: row.joining || null,
  };
}

function Rates() {
  const rates = useRates();
  const set = useSetRate();
  const remove = useDeleteRate();
  const [currency, setCurrency] = useState<Exclude<Currency, "INR">>("USD");
  const [rate, setRate] = useState("");
  const [asOf, setAsOf] = useState(todayLocal);

  return (
    <section className={`${card} space-y-2`} aria-labelledby="rates-heading">
      <h2 id="rates-heading" className="font-semibold">
        Exchange rates you use
      </h2>
      <p className={muted}>
        Rupees for one unit of the currency. They are typed in by you, with the
        date they are from, and an old one is flagged. Nothing is fetched from
        the internet.
      </p>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          set.mutate(
            { currency, to_inr: rate, as_of: asOf },
            { onSuccess: () => setRate("") },
          );
        }}
      >
        <select
          className={select}
          aria-label="Currency"
          value={currency}
          onChange={(e) => setCurrency(e.target.value as typeof currency)}
        >
          {CURRENCIES.filter((c) => c !== "INR").map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
        <input
          className={`${input} w-32`}
          required
          inputMode="decimal"
          placeholder="Rupees"
          aria-label="Rupees per unit"
          value={rate}
          onChange={(e) => setRate(e.target.value)}
        />
        <input
          className={`${input} w-40`}
          type="date"
          required
          aria-label="Rate date"
          value={asOf}
          onChange={(e) => setAsOf(e.target.value)}
        />
        <button type="submit" className={button} disabled={set.isPending}>
          Save rate
        </button>
      </form>
      {(set.error ?? remove.error) && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {(set.error ?? remove.error)?.message}
        </p>
      )}
      <ul className="text-sm">
        {rates.data?.map((r) => (
          <li
            key={r.currency}
            className="flex items-center justify-between gap-2 py-0.5"
          >
            <span>
              1 {r.currency} = {Number(r.to_inr)} INR · {r.as_of}
              {r.stale && (
                <span className="text-amber-700 dark:text-amber-400">
                  {" "}
                  · {r.age_days} days old
                </span>
              )}
            </span>
            <button
              type="button"
              className="text-xs underline"
              onClick={() => remove.mutate(r.currency)}
            >
              Remove
            </button>
          </li>
        ))}
        {rates.data?.length === 0 && (
          <li className={muted}>No rates yet. Rupee offers need none.</li>
        )}
      </ul>
    </section>
  );
}

export function OffersPage() {
  const compare = useCompareOffers();
  const [rows, setRows] = useState<Row[]>([blank(1), blank(2)]);
  const change = (index: number, patch: Partial<Row>) =>
    setRows((current) =>
      current.map((row, i) => (i === index ? { ...row, ...patch } : row)),
    );

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Compare offers</h1>
      <Rates />
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          compare.mutate(rows.map(toOffer));
        }}
      >
        {rows.map((row, index) => (
          <fieldset key={index} className={`${card} grid gap-2 sm:grid-cols-4`}>
            <legend className="px-1 text-sm font-semibold">
              Offer {index + 1}
            </legend>
            <input
              className={input}
              aria-label="Name"
              value={row.name}
              onChange={(e) => change(index, { name: e.target.value })}
            />
            <select
              className={`${select} w-full`}
              aria-label="Currency"
              value={row.currency}
              onChange={(e) =>
                change(index, { currency: e.target.value as Currency })
              }
            >
              {CURRENCIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            <input
              className={input}
              required
              inputMode="decimal"
              placeholder="Fixed per year"
              aria-label="Fixed pay per year"
              value={row.fixed}
              onChange={(e) => change(index, { fixed: e.target.value })}
            />
            <input
              className={input}
              inputMode="decimal"
              placeholder="Variable target per year"
              aria-label="Variable target per year"
              value={row.variable}
              onChange={(e) => change(index, { variable: e.target.value })}
            />
            <input
              className={input}
              inputMode="decimal"
              placeholder="Expected payout %"
              aria-label="Expected payout percent"
              value={row.payout}
              onChange={(e) => change(index, { payout: e.target.value })}
            />
            <input
              className={input}
              inputMode="decimal"
              placeholder="Joining bonus"
              aria-label="Joining bonus"
              value={row.bonus}
              onChange={(e) => change(index, { bonus: e.target.value })}
            />
            <input
              className={input}
              inputMode="decimal"
              placeholder="Equity value per year (your estimate)"
              aria-label="Equity per year"
              value={row.equity}
              onChange={(e) => change(index, { equity: e.target.value })}
            />
            <input
              className={input}
              inputMode="numeric"
              placeholder="Your notice days"
              aria-label="Notice days"
              value={row.notice}
              onChange={(e) => change(index, { notice: e.target.value })}
            />
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <span>Asked to join by</span>
              <input
                className={input}
                type="date"
                value={row.joining}
                onChange={(e) => change(index, { joining: e.target.value })}
              />
            </label>
            {rows.length > 1 && (
              <button
                type="button"
                className={`${button} sm:col-span-2`}
                onClick={() => setRows((r) => r.filter((_, i) => i !== index))}
              >
                Remove this offer
              </button>
            )}
          </fieldset>
        ))}
        <div className="flex flex-wrap gap-2">
          {rows.length < 6 && (
            <button
              type="button"
              className={button}
              onClick={() => setRows((r) => [...r, blank(r.length + 1)])}
            >
              Add an offer
            </button>
          )}
          <button
            type="submit"
            className={primaryButton}
            disabled={compare.isPending}
          >
            Compare
          </button>
        </div>
        {compare.error && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {compare.error.message}
          </p>
        )}
      </form>

      {compare.data && (
        <section
          className={`${card} space-y-3`}
          aria-labelledby="result-heading"
        >
          <h2 id="result-heading" className="font-semibold">
            Result, in rupees per year
          </h2>
          <p className={muted}>{compare.data.note}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Offers compared</caption>
              <thead>
                <tr className="text-left text-zinc-500">
                  <th className="py-1">Offer</th>
                  <th>Rank</th>
                  <th>Steady cash</th>
                  <th>First year</th>
                  <th>Guaranteed</th>
                  <th>Equity</th>
                  <th>Not guaranteed</th>
                  <th>Earliest start</th>
                </tr>
              </thead>
              <tbody>
                {compare.data.offers.map((o) => (
                  <tr
                    key={o.name}
                    className="border-t border-black/5 align-top dark:border-white/10"
                  >
                    <td className="py-1 font-medium">{o.name}</td>
                    <td>
                      {o.rank ?? "n/a"}
                      {o.behind_best_pct && Number(o.behind_best_pct) > 0
                        ? ` (−${o.behind_best_pct}%)`
                        : ""}
                    </td>
                    <td>{money(o.steady_cash_inr)}</td>
                    <td>{money(o.first_year_cash_inr)}</td>
                    <td>{money(o.guaranteed_cash_inr)}</td>
                    <td>{money(o.equity_annual_inr)}</td>
                    <td>
                      {o.variable_share_pct === null
                        ? "n/a"
                        : `${o.variable_share_pct}%`}
                    </td>
                    <td>{o.earliest_start}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {compare.data.offers.map((o) =>
            o.notes.length > 0 ? (
              <div key={o.name} className="text-sm">
                <strong>{o.name}</strong>
                <ul className="list-disc pl-5">
                  {o.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </section>
      )}
    </div>
  );
}
