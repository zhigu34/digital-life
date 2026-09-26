import { api } from "../../api";
import type {
  Expense,
  LedgerAccount,
  LedgerBook,
  LedgerCategory,
  LedgerEntry,
  LedgerPayee,
} from "../../types";

export const listBooks = () => api<LedgerBook[]>("/ledger/books");
export const createBook = (data: Record<string, unknown>) =>
  api<LedgerBook>("/ledger/books", "POST", data);
export const updateBook = (id: number, data: Record<string, unknown>) =>
  api<LedgerBook>(`/ledger/books/${id}`, "PATCH", data);
export const deleteBook = (id: number) => api<void>(`/ledger/books/${id}`, "DELETE");

export const listAccounts = () => api<LedgerAccount[]>("/ledger/accounts");
export const createAccount = (data: Record<string, unknown>) =>
  api<LedgerAccount>("/ledger/accounts", "POST", data);
export const updateAccount = (id: number, data: Record<string, unknown>) =>
  api<LedgerAccount>(`/ledger/accounts/${id}`, "PATCH", data);
export const deleteAccount = (id: number) => api<void>(`/ledger/accounts/${id}`, "DELETE");

export const listCategories = () => api<LedgerCategory[]>("/ledger/categories");
export const createCategory = (data: Record<string, unknown>) =>
  api<LedgerCategory>("/ledger/categories", "POST", data);
export const updateCategory = (id: number, data: Record<string, unknown>) =>
  api<LedgerCategory>(`/ledger/categories/${id}`, "PATCH", data);
export const deleteCategory = (id: number) => api<void>(`/ledger/categories/${id}`, "DELETE");

export const listPayees = () => api<LedgerPayee[]>("/ledger/payees");
export const createPayee = (data: Record<string, unknown>) =>
  api<LedgerPayee>("/ledger/payees", "POST", data);
export const updatePayee = (id: number, data: Record<string, unknown>) =>
  api<LedgerPayee>(`/ledger/payees/${id}`, "PATCH", data);
export const deletePayee = (id: number) => api<void>(`/ledger/payees/${id}`, "DELETE");
export const mergePayee = (id: number, into: number) =>
  api<{ entries: number; expenses: number }>(`/ledger/payees/${id}/merge`, "POST", { into });

/**
 * Entries of one book, or of every book when no id is given. Only this request
 * is scoped: accounts and the dictionaries stay shared across books.
 */
export const listEntries = (bookId?: number | null) =>
  api<LedgerEntry[]>(
    bookId === undefined || bookId === null
      ? "/ledger/entries"
      : `/ledger/entries?book_id=${bookId}`,
  );
export const createEntry = (data: Record<string, unknown>) =>
  api<LedgerEntry>("/ledger/entries", "POST", data);
export const updateEntry = (id: number, data: Record<string, unknown>) =>
  api<LedgerEntry>(`/ledger/entries/${id}`, "PATCH", data);
export const deleteEntry = (id: number) => api<void>(`/ledger/entries/${id}`, "DELETE");

export type PayResult = Expense & { entry_id: number | null };

/**
 * Confirming a bill as paid. An empty body keeps the pre-ledger behaviour (only
 * the due date moves); the bill's own account decides whether an entry follows,
 * and that entry inherits the bill's book.
 */
export const payExpense = (id: number, body: Record<string, unknown> = {}) =>
  api<PayResult>(`/expenses/${id}/pay`, "POST", body);
