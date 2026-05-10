/**
 * Public API — no auth required, uses fetch to bypass axios interceptor.
 */

const BASE = ''; // same origin

export interface PublicReportData {
  stock_name: string;
  stock_code: string;
  report_language: string;
  markdown_content: string;
}

export const publicApi = {
  /**
   * Fetch report data via the public share endpoint.
   * Uses fetch directly to avoid axios 401→redirect interceptor.
   */
  getReportData: async (recordId: number, token: string): Promise<PublicReportData> => {
    const res = await fetch(
      `${BASE}/api/v1/public/report/${recordId}/data?token=${encodeURIComponent(token)}`,
    );
    if (!res.ok) {
      throw new Error(`Failed to load report: ${res.status}`);
    }
    return res.json();
  },
};
