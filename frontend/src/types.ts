/** 与后端返回结构对应的类型定义 */

export interface User {
  id: number;
  username: string;
  email: string;
}

export interface Category {
  id: number;
  name: string;
  type: "income" | "expense";
}

export interface Wallet {
  id: number;
  name: string;
  balance: number;
  transaction_count: number;
}

export interface Transaction {
  id: number;
  category_id: number;
  category_name: string;
  wallet_id: number | null;
  wallet_name: string;
  amount: number;
  type: "income" | "expense";
  note: string;
  occurred_at: string;
}

export interface Budget {
  month: string;
  amount: number;
  spent: number;
}

export interface CategoryStat {
  category_id: number;
  category_name: string;
  total: number;
  percent: number;
}

export interface MonthSummary {
  month: string;
  total_income: number;
  total_expense: number;
  balance: number;
  income_by_category: CategoryStat[];
  expense_by_category: CategoryStat[];
}

export interface TrendPoint {
  month: string;
  income: number;
  expense: number;
}
