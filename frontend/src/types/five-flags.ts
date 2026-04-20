/**
 * Type definitions for Five Flags Stock Pool
 */

export interface ScreenerResult {
  stock_code: string
  stock_name: string
  screener_id: string
  screener_name: string
  screen_date: string
  close_price: number
  match_reason: string
}

export interface Stock {
  stock_code: string
  stock_name: string
}

export interface FiveFlagsApiResponse {
  success: boolean
  data: ScreenerResult[] | null
  error: string | null
}

export interface FiveFlagsStocksApiResponse {
  success: boolean
  data: Stock[]
  error: string | null
}
