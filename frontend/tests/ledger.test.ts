import { describe, expect, it } from "vitest";
import type { LedgerAccount, LedgerEntry, StatsLedgerCategory } from "../src/types";
import {
  accountNet,
  categoryShares,
  entryAccountLabel,
  filterByAccount,
  groupEntriesByDay,
  monthlySummary,
  signedAmount,
} from "../src/features/ledger/ledger";

let nextId = 1;

function entry(overrides: Partial<LedgerEntry> = {}): LedgerEntry {
  return {
    id: nextId++,
    occurred_on: "2026-09-05",
    kind: "expense",
    amount_cents: 2000,
    currency: "CNY",
    account_id: 1,
    from_account_id: null,
    to_account_id: null,
    category_id: null,
    payee_id: null,
    note: "",
    expense_id: null,
    created_at: "2026-09-05T10:00:00",
    ...overrides,
  };
}

const accounts = [
  { id: 1, name: "招行储蓄卡", currency: "CNY" },
  { id: 2, name: "微信零钱", currency: "CNY" },
] as LedgerAccount[];

describe("groupEntriesByDay", () => {
  it("puts the newest day first and the newest entry first inside a day", () => {
    const older = entry({ occurred_on: "2026-09-04" });
    const first = entry({ occurred_on: "2026-09-05" });
    const second = entry({ occurred_on: "2026-09-05" });

    const groups = groupEntriesByDay([older, first, second]);

    expect(groups.map((group) => group.date)).toEqual(["2026-09-05", "2026-09-04"]);
    expect(groups[0]!.entries.map((row) => row.id)).toEqual([second.id, first.id]);
  });

  it("subtotals income and expense per currency and leaves transfers out", () => {
    const groups = groupEntriesByDay([
      entry({ amount_cents: 3000 }),
      entry({ kind: "income", amount_cents: 500000 }),
      entry({ amount_cents: 1200, currency: "USD" }),
      entry({
        kind: "transfer",
        amount_cents: 700,
        account_id: null,
        from_account_id: 1,
        to_account_id: 2,
      }),
    ]);

    expect(groups[0]!.expense).toEqual({ CNY: 3000, USD: 1200 });
    expect(groups[0]!.income).toEqual({ CNY: 500000 });
  });
});

describe("monthlySummary", () => {
  it("counts only the given month and currency, and never transfers", () => {
    const summary = monthlySummary(
      [
        entry({ amount_cents: 3000, category_id: 1 }),
        entry({ kind: "income", amount_cents: 5000 }),
        entry({ occurred_on: "2026-08-31", amount_cents: 900 }),
        entry({ amount_cents: 400, currency: "USD" }),
        entry({
          kind: "transfer",
          amount_cents: 700,
          account_id: null,
          from_account_id: 1,
          to_account_id: 2,
        }),
      ],
      "2026-09",
      "CNY",
    );

    expect(summary).toEqual({ income: 5000, expense: 3000, net: 2000 });
  });
});

describe("filterByAccount", () => {
  it("keeps transfers that touch the account on either side", () => {
    const own = entry({ account_id: 1 });
    const other = entry({ account_id: 2 });
    const outgoing = entry({
      kind: "transfer",
      account_id: null,
      from_account_id: 1,
      to_account_id: 2,
    });
    const unrelated = entry({
      kind: "transfer",
      account_id: null,
      from_account_id: 2,
      to_account_id: 3,
    });

    expect(filterByAccount([own, other, outgoing, unrelated], 1).map((row) => row.id)).toEqual([
      own.id,
      outgoing.id,
    ]);
    expect(filterByAccount([own, other], null)).toHaveLength(2);
  });

  it("keeps each account's monthly net summing to the global net", () => {
    const rows = [
      entry({ account_id: 1, amount_cents: 3000 }),
      entry({ account_id: 2, kind: "income", amount_cents: 5000 }),
      entry({
        kind: "transfer",
        account_id: null,
        amount_cents: 700,
        from_account_id: 1,
        to_account_id: 2,
      }),
    ];

    const perAccount = [1, 2].reduce(
      (sum, id) => sum + accountNet(rows, id, "2026-09", "CNY"),
      0,
    );
    expect(perAccount).toBe(monthlySummary(rows, "2026-09", "CNY").net);
    expect(accountNet(rows, null, "2026-09", "CNY")).toBe(-3000 + 5000);
  });
});

describe("categoryShares", () => {
  const rows: StatsLedgerCategory[] = [
    { category_id: 1, name: "餐饮", kind: "expense", totals: { CNY: 3000 } },
    { category_id: 2, name: "交通", kind: "expense", totals: { CNY: 1000 } },
    { category_id: 3, name: "工资", kind: "income", totals: { CNY: 500000 } },
    { category_id: 4, name: "其他", kind: "expense", totals: {} },
  ];

  it("ranks one kind by amount and drops empty rows", () => {
    const shares = categoryShares(rows, "expense", "CNY");

    expect(shares.map((row) => row.name)).toEqual(["餐饮", "交通"]);
    expect(shares[0]!.share).toBeCloseTo(0.75);
    expect(shares.reduce((sum, row) => sum + row.share, 0)).toBeCloseTo(1);
  });

  it("returns nothing when the currency is absent", () => {
    expect(categoryShares(rows, "expense", "USD")).toEqual([]);
  });
});

describe("signedAmount and account labels", () => {
  const format = (cents: number, currency: string) => `${currency}${cents}`;

  it("always writes the sign so colour is not the only signal", () => {
    expect(signedAmount(2000, "CNY", "expense", format)).toBe("-CNY2000");
    expect(signedAmount(2000, "CNY", "income", format)).toBe("+CNY2000");
    expect(signedAmount(2000, "CNY", "transfer", format)).toBe("CNY2000");
  });

  it("labels the account of a plain entry and both sides of a transfer", () => {
    expect(entryAccountLabel(entry(), accounts)).toBe("招行储蓄卡");
    expect(
      entryAccountLabel(
        entry({
          kind: "transfer",
          account_id: null,
          from_account_id: 1,
          to_account_id: 2,
        }),
        accounts,
      ),
    ).toBe("招行储蓄卡 → 微信零钱");
    expect(entryAccountLabel(entry({ account_id: 99 }), accounts)).toBe("已删除账户");
  });
});
